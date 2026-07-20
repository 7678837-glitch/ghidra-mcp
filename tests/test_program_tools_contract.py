from contextlib import contextmanager
from pathlib import Path

from ghidra_mcp.registry import ToolRegistry
from ghidra_mcp.runtime import GhidraRuntime, ProgramWorkspace


class FakeCompilerSpec:
    def getCompilerSpecID(self) -> str:
        return "default"


class FakeProgram:
    def getName(self) -> str:
        return "sample.bin"

    def getLanguageID(self) -> str:
        return "x86:LE:64:default"

    def getCompilerSpec(self) -> FakeCompilerSpec:
        return FakeCompilerSpec()

    def getImageBase(self) -> str:
        return "00400000"

    def getExecutableFormat(self) -> str:
        return "Executable and Linking Format (ELF)"

    def getMinAddress(self) -> str:
        return "00400000"

    def getMaxAddress(self) -> str:
        return "00401fff"


class FakeAPI:
    def __init__(self, binary: Path) -> None:
        self.binary = binary

    def getCurrentProgram(self) -> FakeProgram:
        return FakeProgram()


class FakePyGhidra:
    def start(self, *, install_dir: Path) -> object:
        return install_dir

    @contextmanager
    def open_program(self, binary_path: Path, **_: object):
        yield FakeAPI(binary_path)


def test_program_tools_cover_open_list_info_and_close(tmp_path: Path) -> None:
    from ghidra_mcp.tools.programs import register_program_tools

    install_dir = tmp_path / "ghidra"
    install_dir.mkdir()
    binary = tmp_path / "sample.bin"
    binary.write_bytes(b"sample")
    workspace = ProgramWorkspace(
        GhidraRuntime(install_dir=install_dir, pyghidra_module=FakePyGhidra())
    )
    registry = ToolRegistry()

    register_program_tools(registry, workspace)
    tools = {tool.name: tool for tool in registry.enabled_tools()}

    assert list(tools) == ["program_open", "program_list", "program_info", "program_close"]

    opened = tools["program_open"].handler(str(binary), analyze=False)
    program_id = opened["program_id"]
    assert opened == {"program_id": program_id, "path": str(binary.resolve())}
    assert tools["program_list"].handler() == [
        {"program_id": program_id, "path": str(binary.resolve())}
    ]
    assert tools["program_info"].handler(program_id) == {
        "program_id": program_id,
        "name": "sample.bin",
        "language": "x86:LE:64:default",
        "compiler": "default",
        "image_base": "00400000",
        "format": "Executable and Linking Format (ELF)",
        "min_address": "00400000",
        "max_address": "00401fff",
    }
    assert tools["program_close"].handler(program_id) == {"closed": program_id}
    assert tools["program_list"].handler() == []
