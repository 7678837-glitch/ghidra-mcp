"""把本地工具注册表绑定到 FastMCP。"""

from mcp.server.fastmcp import FastMCP

from .registry import ToolRegistry


def create_mcp_app(registry: ToolRegistry, *, host: str, port: int) -> FastMCP:
    app = FastMCP("ghidra-mcp", host=host, port=port)
    for tool in registry.enabled_tools():
        app.tool(name=tool.name, description=tool.description)(tool.handler)
    return app
