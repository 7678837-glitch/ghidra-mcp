"""反编译与函数图分析工具。"""

from typing import Any

from ..registry import ToolDefinition, ToolRegistry
from ..runtime import ProgramWorkspace
from .navigation import ToolInputError


def _new_decompiler() -> Any:
    from ghidra.app.decompiler import DecompInterface

    return DecompInterface()


def _function(api: Any, address: str) -> Any:
    resolved = api.toAddr(address)
    if resolved is None:
        raise ToolInputError(f"无法解析地址：{address}")
    function = api.getFunctionContaining(resolved)
    if function is None:
        raise ToolInputError(f"地址未包含在函数中：{address}")
    return function


def _identity(function: Any) -> dict[str, str]:
    return {"name": str(function.getName()), "entry_point": str(function.getEntryPoint())}


def register_analysis_tools(registry: ToolRegistry, workspace: ProgramWorkspace) -> None:
    def decompile_function(
        program_id: str, address: str, timeout_seconds: int = 30
    ) -> dict[str, str]:
        if not 1 <= timeout_seconds <= 300:
            raise ToolInputError("timeout_seconds 必须在 1 到 300 之间")
        api = workspace.get(program_id)
        program = api.getCurrentProgram()
        function = _function(api, address)
        decompiler = _new_decompiler()
        try:
            if not decompiler.openProgram(program):
                raise RuntimeError(f"反编译器无法打开程序：{decompiler.getLastMessage()}")
            results = decompiler.decompileFunction(function, timeout_seconds, None)
            if not results.decompileCompleted():
                raise RuntimeError(f"反编译失败：{decompiler.getLastMessage()}")
            decompiled = results.getDecompiledFunction()
            if decompiled is None:
                raise RuntimeError("反编译完成但没有生成 C 文本")
            return {**_identity(function), "c": str(decompiled.getC())}
        finally:
            decompiler.dispose()

    def call_graph(program_id: str, address: str) -> dict[str, object]:
        api = workspace.get(program_id)
        function = _function(api, address)
        callers = sorted(function.getCallingFunctions(None), key=lambda item: str(item.getEntryPoint()))
        callees = sorted(function.getCalledFunctions(None), key=lambda item: str(item.getEntryPoint()))
        return {
            "function": _identity(function),
            "callers": [_identity(item) for item in callers],
            "callees": [_identity(item) for item in callees],
        }

    def control_flow_graph(program_id: str, address: str) -> dict[str, object]:
        api = workspace.get(program_id)
        function = _function(api, address)
        instructions = list(
            api.getCurrentProgram().getListing().getInstructions(function.getBody(), True)
        )
        if len(instructions) > 10_000:
            raise RuntimeError("函数指令超过 10000 条，拒绝生成过大的控制流图")
        nodes = [str(instruction.getAddress()) for instruction in instructions]
        edges: list[dict[str, str]] = []
        for instruction in instructions:
            source = str(instruction.getAddress())
            fallthrough = instruction.getFallThrough()
            if fallthrough is not None:
                edges.append({"from": source, "to": str(fallthrough), "kind": "fallthrough"})
            for target in instruction.getFlows() or ():
                edges.append({"from": source, "to": str(target), "kind": "flow"})
        return {"function": _identity(function), "nodes": nodes, "edges": edges}

    definitions = (
        ToolDefinition(
            "decompile_function",
            """将包含指定地址的函数反编译为 C 风格文本。

输入输出与副作用：输入程序会话、函数内地址和 1 到 300 秒超时；返回函数身份与 C 文本；只读并在调用后释放反编译器。

何时使用：理解函数高层语义时调用；核对具体机器指令时改用 instructions_list。
""",
            decompile_function,
        ),
        ToolDefinition(
            "call_graph",
            """读取函数的一跳调用者与被调用者。

输入输出与副作用：输入程序会话和函数内地址；返回目标函数、调用者与被调用者身份；只读。

何时使用：定位调用关系和影响范围时调用；分析函数内部跳转结构时改用 control_flow_graph。
""",
            call_graph,
        ),
        ToolDefinition(
            "control_flow_graph",
            """构建函数的指令级控制流边集合。

输入输出与副作用：输入程序会话和函数内地址；返回指令节点以及 fallthrough/flow 边；只读，拒绝超过 10000 条指令的图。

何时使用：分析分支、循环或混淆控制流时调用；跨函数调用关系应改用 call_graph。
""",
            control_flow_graph,
        ),
    )
    for definition in definitions:
        registry.register(definition)
