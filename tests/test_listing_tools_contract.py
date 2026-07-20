from dataclasses import dataclass

import pytest

from ghidra_mcp.registry import ToolRegistry


@dataclass
class FakeInstruction:
    address: str
    mnemonic: str
    operands: tuple[str, ...]
    length: int

    def getAddress(self) -> str:
        return self.address

    def getMnemonicString(self) -> str:
        return self.mnemonic

    def getNumOperands(self) -> int:
        return len(self.operands)

    def getDefaultOperandRepresentation(self, index: int) -> str:
        return self.operands[index]

    def getLength(self) -> int:
        return self.length


@dataclass
class FakeSymbol:
    name: str
    address: str

    def getName(self) -> str:
        return self.name

    def getAddress(self) -> str:
        return self.address

    def getSymbolType(self) -> str:
        return "Function"

    def getSource(self) -> str:
        return "ANALYSIS"

    def isPrimary(self) -> bool:
        return True


@dataclass
class FakeReference:
    source: str
    target: str

    def getFromAddress(self) -> str:
        return self.source

    def getToAddress(self) -> str:
        return self.target

    def getReferenceType(self) -> str:
        return "UNCONDITIONAL_CALL"

    def getOperandIndex(self) -> int:
        return 0

    def isPrimary(self) -> bool:
        return True


@dataclass
class FakeData:
    address: str
    value: str

    def hasStringValue(self) -> bool:
        return True

    def getAddress(self) -> str:
        return self.address

    def getLength(self) -> int:
        return len(self.value) + 1

    def getDataType(self) -> str:
        return "string"

    def getDefaultValueRepresentation(self) -> str:
        return f'"{self.value}"'


class FakeListing:
    def getInstructions(self, *args: object) -> list[FakeInstruction]:
        assert args in ((True,), ("00400010", True))
        return [FakeInstruction("00400010", "MOV", ("EAX", "EBX"), 2)]

    def getDefinedData(self, forward: bool) -> list[FakeData]:
        assert forward is True
        return [FakeData("00401000", "hello")]


class FakeSymbolTable:
    def getAllSymbols(self, include_dynamic: bool) -> list[FakeSymbol]:
        assert include_dynamic is True
        return [FakeSymbol("entry", "00400010")]


class FakeReferenceManager:
    def getReferencesFrom(self, address: str) -> list[FakeReference]:
        return [FakeReference(address, "00400030")]

    def getReferencesTo(self, address: str) -> list[FakeReference]:
        return [FakeReference("00400008", address)]


class FakeProgram:
    def getListing(self) -> FakeListing:
        return FakeListing()

    def getSymbolTable(self) -> FakeSymbolTable:
        return FakeSymbolTable()

    def getReferenceManager(self) -> FakeReferenceManager:
        return FakeReferenceManager()


class FakeAPI:
    def getCurrentProgram(self) -> FakeProgram:
        return FakeProgram()

    def toAddr(self, address: str) -> str | None:
        return address if address.startswith("0040") else None


class FakeWorkspace:
    def get(self, program_id: str) -> FakeAPI:
        assert program_id == "program-1"
        return FakeAPI()


def test_listing_tools_return_stable_json_contracts() -> None:
    from ghidra_mcp.tools.listing import register_listing_tools

    registry = ToolRegistry()
    register_listing_tools(registry, FakeWorkspace())
    tools = {tool.name: tool.handler for tool in registry.enabled_tools()}

    assert list(tools) == ["instructions_list", "symbols_list", "references_list", "strings_list"]
    assert tools["instructions_list"]("program-1", address="00400010") == [
        {
            "address": "00400010",
            "mnemonic": "MOV",
            "operands": ["EAX", "EBX"],
            "length": 2,
        }
    ]
    assert tools["symbols_list"]("program-1") == [
        {
            "name": "entry",
            "address": "00400010",
            "type": "Function",
            "source": "ANALYSIS",
            "primary": True,
        }
    ]
    assert tools["references_list"]("program-1", "00400010", direction="both") == [
        {
            "from": "00400010",
            "to": "00400030",
            "type": "UNCONDITIONAL_CALL",
            "operand_index": 0,
            "primary": True,
            "direction": "from",
        },
        {
            "from": "00400008",
            "to": "00400010",
            "type": "UNCONDITIONAL_CALL",
            "operand_index": 0,
            "primary": True,
            "direction": "to",
        },
    ]
    assert tools["strings_list"]("program-1", contains="ell") == [
        {"address": "00401000", "length": 6, "data_type": "string", "value": '"hello"'}
    ]


def test_listing_tools_validate_direction_address_and_page_size() -> None:
    from ghidra_mcp.tools.listing import ToolInputError, register_listing_tools

    registry = ToolRegistry()
    register_listing_tools(registry, FakeWorkspace())
    tools = {tool.name: tool.handler for tool in registry.enabled_tools()}

    with pytest.raises(ToolInputError, match="limit"):
        tools["instructions_list"]("program-1", limit=0)
    with pytest.raises(ToolInputError, match="direction"):
        tools["references_list"]("program-1", "00400010", direction="sideways")
    with pytest.raises(ToolInputError, match="地址"):
        tools["references_list"]("program-1", "invalid")


def test_listing_page_does_not_consume_past_requested_window() -> None:
    from ghidra_mcp.tools.listing import _page

    def guarded():
        yield "skip"
        yield "first"
        yield "second"
        raise AssertionError("分页读取越过 offset + limit")

    assert _page(guarded(), offset=1, limit=2) == ["first", "second"]


def test_references_stop_after_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    from ghidra_mcp.tools.listing import register_listing_tools

    def guarded_from(_self, address):
        yield FakeReference(address, "00400030")
        raise AssertionError("引用读取越过 limit")

    def forbidden_to(_self, _address):
        raise AssertionError("已有足够结果后不应读取另一方向")

    monkeypatch.setattr(FakeReferenceManager, "getReferencesFrom", guarded_from)
    monkeypatch.setattr(FakeReferenceManager, "getReferencesTo", forbidden_to)
    registry = ToolRegistry()
    register_listing_tools(registry, FakeWorkspace())
    tools = {tool.name: tool.handler for tool in registry.enabled_tools()}

    assert len(tools["references_list"]("program-1", "00400010", limit=1)) == 1
