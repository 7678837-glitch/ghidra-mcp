import asyncio
from contextlib import contextmanager
from pathlib import Path

import pytest

from ghidra_mcp.registry import ToolDefinition, ToolRegistry


DESCRIPTION = """回显输入文本。

输入输出与副作用：输入文本；返回相同文本；只读。

何时使用：验证 MCP 调用链；真实程序分析应使用对应任务工具。
"""


def test_mcp_app_exposes_registry_tools_without_schema_relay() -> None:
    from ghidra_mcp.server import create_mcp_app

    registry = ToolRegistry()

    def echo(text: str) -> str:
        return text

    registry.register(ToolDefinition("echo", DESCRIPTION, echo))
    app = create_mcp_app(registry, host="127.0.0.1", port=8765)

    tools = asyncio.run(app.list_tools())

    assert [tool.name for tool in tools] == ["echo"]
    assert tools[0].description == DESCRIPTION
    assert tools[0].inputSchema["properties"]["text"]["type"] == "string"


class FakePyGhidra:
    def __init__(self) -> None:
        self.start_calls: list[Path] = []
        self.open_calls: list[Path] = []
        self.open_options: list[dict[str, object]] = []
        self.closed: list[Path] = []

    def start(self, *, install_dir: Path) -> object:
        self.start_calls.append(install_dir)
        return object()

    @contextmanager
    def _program_context_factory(self, binary_path: Path, **options: object):
        self.open_calls.append(binary_path)
        self.open_options.append(options)
        try:
            yield {"binary": binary_path}
        finally:
            self.closed.append(binary_path)


def test_workspace_starts_jvm_once_and_owns_program_lifecycle(tmp_path: Path) -> None:
    from ghidra_mcp.runtime import GhidraRuntime, ProgramWorkspace

    install_dir = tmp_path / "ghidra"
    install_dir.mkdir()
    binary = tmp_path / "sample.bin"
    binary.write_bytes(b"sample")
    fake = FakePyGhidra()
    runtime = GhidraRuntime(install_dir=install_dir, pyghidra_module=fake)
    workspace = ProgramWorkspace(runtime)

    first_id = workspace.open(binary)
    second_id = workspace.open(binary)

    assert fake.start_calls == [install_dir]
    assert workspace.get(first_id)["binary"] == binary.resolve()
    assert first_id != second_id

    workspace.close(first_id)
    assert fake.closed == [binary.resolve()]
    workspace.close_all()
    assert fake.closed == [binary.resolve(), binary.resolve()]


def test_workspace_rejects_missing_binary_before_starting_jvm(tmp_path: Path) -> None:
    from ghidra_mcp.runtime import GhidraRuntime, ProgramWorkspace, WorkspaceError

    install_dir = tmp_path / "ghidra"
    install_dir.mkdir()
    fake = FakePyGhidra()
    workspace = ProgramWorkspace(GhidraRuntime(install_dir, pyghidra_module=fake))

    with pytest.raises(WorkspaceError, match="不存在"):
        workspace.open(tmp_path / "missing.bin")

    assert fake.start_calls == []


def test_workspace_uses_configured_persistent_project_root(tmp_path: Path) -> None:
    from ghidra_mcp.runtime import GhidraRuntime, ProgramWorkspace

    install_dir = tmp_path / "ghidra"
    install_dir.mkdir()
    binary = tmp_path / "sample.bin"
    binary.write_bytes(b"sample")
    project_root = tmp_path / "projects"
    fake = FakePyGhidra()
    workspace = ProgramWorkspace(
        GhidraRuntime(install_dir, pyghidra_module=fake), project_location=project_root
    )

    program_id = workspace.open(binary)
    workspace.close(program_id)

    assert project_root.is_dir()
    assert fake.open_options[0]["project_location"] == project_root.resolve()
