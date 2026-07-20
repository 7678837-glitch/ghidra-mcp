import asyncio
from contextlib import contextmanager
from pathlib import Path
import threading
import time

import pytest
from starlette.testclient import TestClient

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


def test_http_health_is_public_and_mcp_requires_the_configured_bearer_token() -> None:
    from ghidra_mcp.server import create_mcp_app

    registry = ToolRegistry()

    def echo(text: str) -> str:
        return text

    registry.register(ToolDefinition("echo", DESCRIPTION, echo))
    app = create_mcp_app(
        registry,
        host="127.0.0.1",
        port=8765,
        auth_token="private-test-token",
        version="20260720.1",
        git_commit="abc123def456",
    )

    with TestClient(app.streamable_http_app()) as client:
        health = client.get("/health")
        missing = client.post("/mcp", json={})
        wrong = client.post(
            "/mcp",
            headers={"Authorization": "Bearer wrong-token"},
            json={},
        )
        accepted = client.post(
            "/mcp",
            headers={"Authorization": "Bearer private-test-token"},
            json={},
        )

    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "version": "20260720.1",
        "git_commit": "abc123def456",
        "schema_version": health.json()["schema_version"],
    }
    assert len(health.json()["schema_version"]) == 16
    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert accepted.status_code != 401


def test_token_verifier_rejects_unicode_without_raising() -> None:
    from ghidra_mcp.server import StaticTokenVerifier

    verifier = StaticTokenVerifier("ascii-test-token")

    assert asyncio.run(verifier.verify_token("令牌")) is None


def test_sync_tools_use_one_worker_without_blocking_event_loop() -> None:
    from ghidra_mcp.server import GhidraToolExecutor, create_mcp_app

    registry = ToolRegistry()
    worker_threads: list[int] = []

    def slow(value: int) -> int:
        worker_threads.append(threading.get_ident())
        time.sleep(0.1)
        return value

    registry.register(ToolDefinition("slow", DESCRIPTION, slow))
    executor = GhidraToolExecutor()
    app = create_mcp_app(
        registry,
        host="127.0.0.1",
        port=8765,
        tool_executor=executor,
    )
    tool = app._tool_manager._tools["slow"]

    async def exercise() -> None:
        first = asyncio.create_task(tool.run({"value": 1}))
        await asyncio.sleep(0.01)
        assert not first.done()
        assert await first == 1
        assert await tool.run({"value": 2}) == 2

    try:
        asyncio.run(exercise())
    finally:
        executor.shutdown()

    assert len(set(worker_threads)) == 1
    assert worker_threads[0] != threading.get_ident()


class FakePyGhidra:
    def __init__(self) -> None:
        self.start_calls: list[Path] = []
        self.open_calls: list[Path] = []
        self.open_options: list[dict[str, object]] = []
        self.closed: list[Path] = []

    def start(self, *, install_dir: Path) -> object:
        self.start_calls.append(install_dir)
        return object()

    def task_monitor(self) -> object:
        return object()

    @contextmanager
    def _program_context_factory(self, binary_path: Path, **options: object):
        self.open_calls.append(binary_path)
        self.open_options.append(options)
        try:
            yield FakeSavedAPI(binary_path)
        finally:
            self.closed.append(binary_path)


class FakeSavedProgram:
    def __init__(self) -> None:
        self.save_calls = 0

    def save(self, _: str, __: object) -> None:
        self.save_calls += 1


class FakeSavedAPI(dict[str, Path]):
    def __init__(self, binary: Path) -> None:
        super().__init__(binary=binary)
        self.program = FakeSavedProgram()

    def getCurrentProgram(self) -> FakeSavedProgram:
        return self.program


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


def test_workspace_rejects_paths_outside_input_root_and_symlink_escape(tmp_path: Path) -> None:
    from ghidra_mcp.runtime import GhidraRuntime, ProgramWorkspace, WorkspaceError

    install_dir = tmp_path / "ghidra"
    install_dir.mkdir()
    input_root = tmp_path / "input"
    input_root.mkdir()
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    escape = input_root / "escape.bin"
    escape.symlink_to(outside)
    fake = FakePyGhidra()
    workspace = ProgramWorkspace(
        GhidraRuntime(install_dir, pyghidra_module=fake), input_root=input_root
    )

    for path in (outside, escape):
        with pytest.raises(WorkspaceError, match="输入根目录"):
            workspace.open(path)

    assert fake.start_calls == []


def test_workspace_project_identity_uses_canonical_path_and_content(tmp_path: Path) -> None:
    from ghidra_mcp.runtime import GhidraRuntime, ProgramWorkspace

    install_dir = tmp_path / "ghidra"
    install_dir.mkdir()
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / "same.bin"
    second = second_dir / "same.bin"
    first.write_bytes(b"same contents")
    second.write_bytes(b"same contents")
    fake = FakePyGhidra()
    workspace = ProgramWorkspace(GhidraRuntime(install_dir, pyghidra_module=fake))

    first_id = workspace.open(first)
    workspace.close(first_id)
    unchanged_id = workspace.open(first)
    workspace.close(unchanged_id)
    second_id = workspace.open(second)
    workspace.close(second_id)
    first.write_bytes(b"updated contents")
    updated_id = workspace.open(first)
    workspace.close(updated_id)

    project_names = [option["project_name"] for option in fake.open_options]
    assert len(set(project_names)) == 3
    assert project_names[0] == project_names[1]
    assert all(str(name).startswith("same.bin-") for name in project_names)


class RetryableCloseContext:
    def __init__(self, binary: Path) -> None:
        self.api = FakeSavedAPI(binary)
        self.fail = True

    def __enter__(self):
        return self.api

    def __exit__(self, *_: object) -> None:
        if self.fail:
            self.fail = False
            raise RuntimeError("save failed")


class RetryableClosePyGhidra(FakePyGhidra):
    def _program_context_factory(self, binary_path: Path, **options: object):
        self.open_calls.append(binary_path)
        self.open_options.append(options)
        return RetryableCloseContext(binary_path)


def test_workspace_close_removes_saved_session_when_context_exit_fails(tmp_path: Path) -> None:
    from ghidra_mcp.runtime import GhidraRuntime, ProgramWorkspace, WorkspaceError

    install_dir = tmp_path / "ghidra"
    install_dir.mkdir()
    binary = tmp_path / "sample.bin"
    binary.write_bytes(b"sample")
    workspace = ProgramWorkspace(
        GhidraRuntime(install_dir, pyghidra_module=RetryableClosePyGhidra())
    )
    program_id = workspace.open(binary)

    with pytest.raises(RuntimeError, match="save failed"):
        workspace.close(program_id)

    with pytest.raises(WorkspaceError, match="程序会话不存在"):
        workspace.get(program_id)
    assert workspace.list_open() == []


class RetryableSaveProgram(FakeSavedProgram):
    def save(self, _: str, __: object) -> None:
        self.save_calls += 1
        if self.save_calls == 1:
            raise RuntimeError("disk unavailable")


class RetryableSaveAPI(FakeSavedAPI):
    def __init__(self, binary: Path) -> None:
        super().__init__(binary)
        self.program = RetryableSaveProgram()


class RetryableSavePyGhidra(FakePyGhidra):
    @contextmanager
    def _program_context_factory(self, binary_path: Path, **options: object):
        self.open_calls.append(binary_path)
        self.open_options.append(options)
        yield RetryableSaveAPI(binary_path)


def test_workspace_save_failure_keeps_session_available_for_retry(tmp_path: Path) -> None:
    from ghidra_mcp.runtime import GhidraRuntime, ProgramWorkspace

    install_dir = tmp_path / "ghidra"
    install_dir.mkdir()
    binary = tmp_path / "sample.bin"
    binary.write_bytes(b"sample")
    workspace = ProgramWorkspace(
        GhidraRuntime(install_dir, pyghidra_module=RetryableSavePyGhidra())
    )
    program_id = workspace.open(binary)

    with pytest.raises(RuntimeError, match="disk unavailable"):
        workspace.save(program_id)

    assert workspace.get(program_id)["binary"] == binary.resolve()
    workspace.save(program_id)
    workspace.close(program_id)
