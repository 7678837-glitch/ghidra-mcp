"""指令、符号、引用与字符串只读工具。"""

from itertools import islice
from typing import Any, Iterable

from ..registry import ToolDefinition, ToolRegistry
from ..runtime import ProgramWorkspace
from .navigation import ToolInputError


def _page(values: Iterable[Any], *, offset: int, limit: int) -> list[Any]:
    if offset < 0:
        raise ToolInputError("offset 不得小于 0")
    if not 1 <= limit <= 1000:
        raise ToolInputError("limit 必须在 1 到 1000 之间")
    return list(islice(values, offset, offset + limit))


def _address(api: Any, value: str) -> Any:
    address = api.toAddr(value)
    if address is None:
        raise ToolInputError(f"无法解析地址：{value}")
    return address


def _reference_json(reference: Any, direction: str) -> dict[str, object]:
    return {
        "from": str(reference.getFromAddress()),
        "to": str(reference.getToAddress()),
        "type": str(reference.getReferenceType()),
        "operand_index": int(reference.getOperandIndex()),
        "primary": bool(reference.isPrimary()),
        "direction": direction,
    }


def register_listing_tools(registry: ToolRegistry, workspace: ProgramWorkspace) -> None:
    def instructions_list(
        program_id: str, address: str | None = None, offset: int = 0, limit: int = 100
    ) -> list[dict[str, object]]:
        api = workspace.get(program_id)
        listing = api.getCurrentProgram().getListing()
        iterator = (
            listing.getInstructions(True)
            if address is None
            else listing.getInstructions(_address(api, address), True)
        )
        instructions = _page(iterator, offset=offset, limit=limit)
        return [
            {
                "address": str(instruction.getAddress()),
                "mnemonic": str(instruction.getMnemonicString()),
                "operands": [
                    str(instruction.getDefaultOperandRepresentation(index))
                    for index in range(instruction.getNumOperands())
                ],
                "length": int(instruction.getLength()),
            }
            for instruction in instructions
        ]

    def symbols_list(
        program_id: str, contains: str | None = None, offset: int = 0, limit: int = 100
    ) -> list[dict[str, object]]:
        program = workspace.get(program_id).getCurrentProgram()
        symbols = program.getSymbolTable().getAllSymbols(True)
        if contains is not None:
            symbols = (symbol for symbol in symbols if contains in str(symbol.getName()))
        return [
            {
                "name": str(symbol.getName()),
                "address": str(symbol.getAddress()),
                "type": str(symbol.getSymbolType()),
                "source": str(symbol.getSource()),
                "primary": bool(symbol.isPrimary()),
            }
            for symbol in _page(symbols, offset=offset, limit=limit)
        ]

    def references_list(
        program_id: str, address: str, direction: str = "both", limit: int = 100
    ) -> list[dict[str, object]]:
        if direction not in {"from", "to", "both"}:
            raise ToolInputError("direction 必须是 from、to 或 both")
        if not 1 <= limit <= 1000:
            raise ToolInputError("limit 必须在 1 到 1000 之间")
        api = workspace.get(program_id)
        resolved = _address(api, address)
        manager = api.getCurrentProgram().getReferenceManager()
        def references() -> Iterable[dict[str, object]]:
            if direction in {"from", "both"}:
                for reference in manager.getReferencesFrom(resolved):
                    yield _reference_json(reference, "from")
            if direction in {"to", "both"}:
                for reference in manager.getReferencesTo(resolved):
                    yield _reference_json(reference, "to")

        return list(islice(references(), limit))

    def strings_list(
        program_id: str, contains: str | None = None, offset: int = 0, limit: int = 100
    ) -> list[dict[str, object]]:
        listing = workspace.get(program_id).getCurrentProgram().getListing()
        values = (data for data in listing.getDefinedData(True) if data.hasStringValue())
        if contains is not None:
            values = (
                data
                for data in values
                if contains in str(data.getDefaultValueRepresentation())
            )
        return [
            {
                "address": str(data.getAddress()),
                "length": int(data.getLength()),
                "data_type": str(data.getDataType()),
                "value": str(data.getDefaultValueRepresentation()),
            }
            for data in _page(values, offset=offset, limit=limit)
        ]

    definitions = (
        ToolDefinition(
            "instructions_list",
            """从程序起点或指定地址分页读取指令。

输入输出与副作用：输入程序会话、可选起始地址和分页参数；返回地址、助记符、操作数与长度；只读。

何时使用：检查具体机器指令或验证反编译结果时调用；只需原始字节时改用 memory_read。
""",
            instructions_list,
        ),
        ToolDefinition(
            "symbols_list",
            """分页列出符号并可按名称片段过滤。

输入输出与副作用：输入程序会话、可选名称片段和分页参数；返回名称、地址、类型、来源与主符号状态；只读。

何时使用：按名称发现函数、标签或外部符号时调用；只需函数集合时优先使用 functions_list。
""",
            symbols_list,
        ),
        ToolDefinition(
            "references_list",
            """读取指定地址的入向、出向或双向引用。

输入输出与副作用：输入程序会话、地址、方向和数量上限；返回源、目标、类型、操作数索引及主引用状态；只读。

何时使用：追踪调用者、被调用者或数据交叉引用时调用；需要完整函数集合时改用 functions_list。
""",
            references_list,
        ),
        ToolDefinition(
            "strings_list",
            """分页列出已定义字符串并可按内容过滤。

输入输出与副作用：输入程序会话、可选内容片段和分页参数；返回地址、长度、数据类型与显示值；只读。

何时使用：从文本线索定位行为和引用时调用；搜索任意原始字节模式时不应使用本工具。
""",
            strings_list,
        ),
    )
    for definition in definitions:
        registry.register(definition)
