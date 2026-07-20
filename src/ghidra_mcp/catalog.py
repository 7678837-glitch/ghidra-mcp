"""默认工具集的唯一装配入口。"""

from .registry import ToolRegistry
from .runtime import ProgramWorkspace
from .tools.listing import register_listing_tools
from .tools.navigation import register_navigation_tools
from .tools.programs import register_program_tools


def build_default_registry(workspace: ProgramWorkspace) -> ToolRegistry:
    registry = ToolRegistry()
    register_program_tools(registry, workspace)
    register_navigation_tools(registry, workspace)
    register_listing_tools(registry, workspace)
    return registry
