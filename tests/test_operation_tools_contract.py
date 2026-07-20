import pytest

from ghidra_mcp.registry import ToolRegistry


class FakeAddress(str):
    def add(self, offset):
        return FakeAddress(f"{int(self, 16) + offset:08x}")


class FakeBlock:
    def getStart(self): return FakeAddress("00400000")
    def getSize(self): return 6
    def isInitialized(self): return True


class FakeMemory:
    def getBlocks(self): return [FakeBlock()]


class FakeDataType:
    def __str__(self): return "dword"
    def getName(self): return "dword"
    def getPathName(self): return "/dword"
    def getLength(self): return 4
    def getDescription(self): return "32-bit"


class FakeDataTypeManager:
    def getDataType(self, path): return FakeDataType() if path == "/dword" else None


class FakeTag:
    def getName(self): return "reviewed"
    def getComment(self): return ""


class FakeFunction:
    def addTag(self, name): return name == "reviewed"
    def removeTag(self, name): return None
    def getTags(self): return [FakeTag()]


class FakeBookmark:
    pass


class FakeBookmarkManager:
    def __init__(self): self.current = None
    def setBookmark(self, address, kind, category, text):
        self.current = (address, kind, category, text)
        return FakeBookmark()
    def getBookmark(self, address, kind, category): return FakeBookmark()
    def removeBookmark(self, bookmark): self.current = None


class FakeListing:
    def createData(self, address, data_type): return type("Data", (), {"getAddress": lambda self: address, "getLength": lambda self: 4, "getDataType": lambda self: data_type})()


class FakeProgram:
    def __init__(self):
        self.events = []
        self.bookmarks = FakeBookmarkManager()
    def startTransaction(self, name):
        self.events.append(("start", name))
        return 1
    def endTransaction(self, transaction_id, commit): self.events.append(("end", commit))
    def getMemory(self): return FakeMemory()
    def getFunctionManager(self): return type("FM", (), {"getFunctionCount": lambda self: 3})()
    def getDataTypeManager(self): return FakeDataTypeManager()
    def getListing(self): return FakeListing()
    def getBookmarkManager(self): return self.bookmarks


class FakeAPI:
    def __init__(self):
        self.program = FakeProgram()
        self.analyzed = False
    def getCurrentProgram(self): return self.program
    def getBytes(self, address, length): return b"AABBAA"[:length]
    def toAddr(self, address): return FakeAddress(address) if address.startswith("004") else None
    def getFunctionContaining(self, address): return FakeFunction()
    def analyzeAll(self, program): self.analyzed = True


class FakeWorkspace:
    def __init__(self):
        self.api = FakeAPI()
        self.saved = []
    def get(self, program_id): return self.api
    def save(self, program_id): self.saved.append(program_id)


def test_operation_tools_search_analyze_and_commit_mutations():
    from ghidra_mcp.tools.operations import register_operation_tools

    workspace = FakeWorkspace()
    registry = ToolRegistry()
    register_operation_tools(registry, workspace)
    tools = {tool.name: tool.handler for tool in registry.enabled_tools()}

    assert list(tools) == ["memory_search", "analysis_run", "data_type_get", "data_type_apply", "function_tag_update", "bookmark_set"]
    assert tools["memory_search"]("p", "4242") == ["00400002"]
    assert tools["analysis_run"]("p")["functions_after"] == 3
    assert tools["data_type_get"]("p", "/dword")["length"] == 4
    assert tools["data_type_apply"]("p", "00400000", "/dword")["data_type"] == "dword"
    assert tools["function_tag_update"]("p", "00400000", "add", "reviewed")["tags"][0]["name"] == "reviewed"
    assert tools["bookmark_set"]("p", "00400000", "Analysis", "Review", "inspect")["comment"] == "inspect"
    assert all(event == ("end", True) for event in workspace.api.program.events if event[0] == "end")
    assert workspace.saved == ["p"] * 4


def test_operation_tools_reject_unbounded_or_ambiguous_inputs():
    from ghidra_mcp.tools.operations import register_operation_tools

    registry = ToolRegistry()
    register_operation_tools(registry, FakeWorkspace())
    tools = {tool.name: tool.handler for tool in registry.enabled_tools()}
    with pytest.raises(ValueError, match="十六进制"):
        tools["memory_search"]("p", "xyz")
    with pytest.raises(ValueError, match="action"):
        tools["function_tag_update"]("p", "00400000", "toggle", "reviewed")
