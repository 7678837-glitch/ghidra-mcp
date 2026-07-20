"""ghidra-mcp 命令行入口。"""

from .config import load_settings
from .service import create_service


def main() -> None:
    create_service(load_settings()).run()
