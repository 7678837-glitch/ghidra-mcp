"""完整 MCP 服务对象的装配与退出清理。"""

from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import FastMCP

from .catalog import build_default_registry
from .config import ConfigurationError, Settings
from .runtime import GhidraRuntime, ProgramWorkspace
from .server import create_mcp_app


@dataclass(slots=True)
class MCPService:
    settings: Settings
    app: FastMCP
    workspace: ProgramWorkspace

    def run(self) -> None:
        try:
            self.app.run(transport=self.settings.transport)  # type: ignore[arg-type]
        finally:
            self.workspace.close_all()


def create_service(settings: Settings, *, pyghidra_module: Any | None = None) -> MCPService:
    if settings.install_dir is None:
        raise ConfigurationError("必须通过 GHIDRA_INSTALL_DIR 或 TOML 配置 Ghidra 安装目录")
    runtime = GhidraRuntime(settings.install_dir, pyghidra_module=pyghidra_module)
    workspace = ProgramWorkspace(runtime, project_location=settings.storage_root)
    registry = build_default_registry(workspace)
    app = create_mcp_app(registry, host=settings.host, port=settings.port)
    return MCPService(settings=settings, app=app, workspace=workspace)
