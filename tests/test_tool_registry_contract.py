import pytest


VALID_DESCRIPTION = """读取程序概要信息。

输入输出与副作用：输入当前程序标识；返回架构、映像基址和分析状态；只读。

何时使用：开始分析时建立上下文；需要枚举函数时改用 functions_list。
"""


def test_default_registry_never_exposes_more_than_40_tools() -> None:
    from ghidra_mcp.registry import ToolRegistry

    registry = ToolRegistry()

    assert len(registry.enabled_tools()) <= 40


def test_tool_description_requires_three_sections() -> None:
    from ghidra_mcp.registry import DescriptionError, ToolDefinition

    with pytest.raises(DescriptionError, match="输入输出与副作用"):
        ToolDefinition(name="program_info", description="读取程序概要信息。", handler=lambda: None)

    tool = ToolDefinition(name="program_info", description=VALID_DESCRIPTION, handler=lambda: None)
    assert tool.name == "program_info"


def test_duplicate_and_batch_alias_names_are_rejected() -> None:
    from ghidra_mcp.registry import RegistryError, ToolDefinition, ToolRegistry

    registry = ToolRegistry()
    registry.register(ToolDefinition("program_info", VALID_DESCRIPTION, lambda: None))

    with pytest.raises(RegistryError, match="already registered"):
        registry.register(ToolDefinition("program_info", VALID_DESCRIPTION, lambda: None))

    with pytest.raises(RegistryError, match="batch|bulk"):
        registry.register(ToolDefinition("program_info_batch", VALID_DESCRIPTION, lambda: None))
