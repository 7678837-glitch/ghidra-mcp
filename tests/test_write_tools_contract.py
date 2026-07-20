from dataclasses import dataclass

import pytest

from ghidra_mcp.registry import ToolRegistry


class FakeProgram:
    def __init__(self) -> None:
        self.events: list[tuple[object, ...]] = []
        self.listing = FakeListing(self)
        self.symbol_table = FakeSymbolTable(self)

    def startTransaction(self, description: str) -> int:
        self.events.append(("start", description))
        return len(self.events)

    def endTransaction(self, transaction_id: int, commit: bool) -> None:
        self.events.append(("end", transaction_id, commit))

    def getListing(self) -> "FakeListing":
        return self.listing

    def getSymbolTable(self) -> "FakeSymbolTable":
        return self.symbol_table


@dataclass
class FakeFunction:
    program: FakeProgram
    name: str = "FUN_00400010"
    entry: str = "00400010"
    fail_rename: bool = False

    def getName(self) -> str:
        return self.name

    def getEntryPoint(self) -> str:
        return self.entry

    def setName(self, name: str, source: object) -> None:
        if self.fail_rename:
            raise RuntimeError("rename failed")
        self.program.events.append(("function_name", name, source))
        self.name = name


class FakeSymbol:
    def __init__(self, program: FakeProgram) -> None:
        self.program = program
        self.name = "label_1"

    def getName(self) -> str:
        return self.name

    def getAddress(self) -> str:
        return "00400020"

    def setName(self, name: str, source: object) -> None:
        self.program.events.append(("symbol_name", name, source))
        self.name = name


class FakeSymbolTable:
    def __init__(self, program: FakeProgram) -> None:
        self.symbol = FakeSymbol(program)

    def getPrimarySymbol(self, address: str) -> FakeSymbol | None:
        return self.symbol if address == "00400020" else None


class FakeListing:
    def __init__(self, program: FakeProgram) -> None:
        self.program = program

    def setComment(self, address: str, kind: object, text: str | None) -> None:
        self.program.events.append(("comment", address, kind, text))


class FakeAPI:
    def __init__(self, *, fail_rename: bool = False) -> None:
        self.program = FakeProgram()
        self.function = FakeFunction(self.program, fail_rename=fail_rename)

    def getCurrentProgram(self) -> FakeProgram:
        return self.program

    def toAddr(self, address: str) -> str | None:
        return address if address.startswith("0040") else None

    def getFunctionContaining(self, address: str) -> FakeFunction | None:
        return self.function if address in {"00400010", "00400011"} else None

    def getFunctionAt(self, address: str) -> FakeFunction | None:
        return self.function if address == "00400010" else None

    def createFunction(self, address: str, name: str) -> FakeFunction:
        self.program.events.append(("create", address, name))
        return FakeFunction(self.program, name=name, entry=address)

    def removeFunction(self, function: FakeFunction) -> None:
        self.program.events.append(("delete", function.entry))


class FakeWorkspace:
    def __init__(self, *, fail_rename: bool = False) -> None:
        self.api = FakeAPI(fail_rename=fail_rename)
        self.saved: list[str] = []

    def get(self, program_id: str) -> FakeAPI:
        assert program_id == "program-1"
        return self.api

    def save(self, program_id: str) -> None:
        self.saved.append(program_id)


def _tools(workspace: FakeWorkspace, monkeypatch: pytest.MonkeyPatch):
    from ghidra_mcp.tools import writes

    monkeypatch.setattr(writes, "_user_defined_source", lambda: "USER_DEFINED")
    monkeypatch.setattr(writes, "_comment_type", lambda value: value.upper())
    registry = ToolRegistry()
    writes.register_write_tools(registry, workspace)
    return {tool.name: tool.handler for tool in registry.enabled_tools()}


def test_write_tools_commit_successful_transactions(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = FakeWorkspace()
    tools = _tools(workspace, monkeypatch)

    assert list(tools) == [
        "function_rename",
        "symbol_rename",
        "comment_set",
        "function_create",
        "function_delete",
    ]
    assert tools["function_rename"]("program-1", "00400011", "worker")["name"] == "worker"
    assert tools["symbol_rename"]("program-1", "00400020", "target")["name"] == "target"
    assert tools["comment_set"]("program-1", "00400020", "eol", "checked") == {
        "address": "00400020",
        "kind": "eol",
        "text": "checked",
    }
    assert tools["function_create"]("program-1", "00400030", "created") == {
        "name": "created",
        "entry_point": "00400030",
    }
    assert tools["function_delete"]("program-1", "00400010") == {
        "deleted": "00400010"
    }
    ends = [event for event in workspace.api.program.events if event[0] == "end"]
    assert len(ends) == 5
    assert all(event[2] is True for event in ends)
    assert workspace.saved == ["program-1"] * 5


def test_write_tool_rolls_back_when_mutation_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = FakeWorkspace(fail_rename=True)
    tools = _tools(workspace, monkeypatch)

    with pytest.raises(RuntimeError, match="rename failed"):
        tools["function_rename"]("program-1", "00400010", "worker")

    assert workspace.api.program.events[-1][0] == "end"
    assert workspace.api.program.events[-1][2] is False
    assert workspace.saved == []
