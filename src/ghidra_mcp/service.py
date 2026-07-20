"""完整 MCP 服务对象的装配与退出清理。"""

from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import FastMCP

from .catalog import build_default_registry
from .config import ConfigurationError, Settings
from .runtime import GhidraRuntime, ProgramWorkspace
from .server import GhidraToolExecutor, create_mcp_app


@dataclass(slots=True)
class MCPService:
    settings: Settings
    app: FastMCP
    workspace: ProgramWorkspace
    tool_executor: GhidraToolExecutor

    def run(self) -> None:
        try:
            self.app.run(transport=self.settings.transport)  # type: ignore[arg-type]
        finally:
            try:
                self.tool_executor.run_sync(self.workspace.close_all)
            finally:
                self.tool_executor.shutdown()


def create_service(settings: Settings, *, pyghidra_module: Any | None = None) -> MCPService:
    if settings.install_dir is None:
        raise ConfigurationError("必须通过 GHIDRA_INSTALL_DIR 或 TOML 配置 Ghidra 安装目录")
    if settings.transport == "streamable-http" and (
        settings.auth_token is None or not settings.auth_token.strip()
    ):
        raise ConfigurationError("streamable-http 必须设置 GHIDRA_MCP_AUTH_TOKEN")
    if settings.transport == "streamable-http" and settings.input_root is None:
        raise ConfigurationError("streamable-http 必须设置 GHIDRA_MCP_INPUT_ROOT")
    runtime = GhidraRuntime(settings.install_dir, pyghidra_module=pyghidra_module)
    workspace = ProgramWorkspace(
        runtime,
        project_location=settings.storage_root,
        input_root=settings.input_root,
    )
    registry = build_default_registry(workspace)
    tool_executor = GhidraToolExecutor()
    app = create_mcp_app(
        registry,
        host=settings.host,
        port=settings.port,
        auth_token=settings.auth_token if settings.transport == "streamable-http" else None,
        tool_executor=tool_executor,
    )
    return MCPService(
        settings=settings,
        app=app,
        workspace=workspace,
        tool_executor=tool_executor,
    )
