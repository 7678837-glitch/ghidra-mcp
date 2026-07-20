import asyncio
from pathlib import Path


class FakePyGhidra:
    def __init__(self) -> None:
        self.started = False

    def start(self, *, install_dir: Path) -> object:
        self.started = True
        return install_dir


def test_service_builds_default_catalog_without_starting_jvm(tmp_path: Path) -> None:
    from ghidra_mcp.config import Settings
    from ghidra_mcp.service import create_service

    install_dir = tmp_path / "ghidra"
    install_dir.mkdir()
    fake = FakePyGhidra()
    storage_root = tmp_path / "projects"
    settings = Settings(install_dir=install_dir, storage_root=storage_root)

    service = create_service(settings, pyghidra_module=fake)
    tools = asyncio.run(service.app.list_tools())

    assert len(tools) == 34
    assert fake.started is False
    assert service.settings is settings
    assert service.workspace.project_location == storage_root.resolve()
