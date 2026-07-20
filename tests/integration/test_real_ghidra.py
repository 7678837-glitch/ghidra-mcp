import os
from pathlib import Path

import pytest

from ghidra_mcp.catalog import build_default_registry
from ghidra_mcp.runtime import GhidraRuntime, ProgramWorkspace


FIXTURES = Path(__file__).parents[1] / "fixtures" / "generated"


@pytest.mark.integration
def test_real_elf_shared_libraries_cover_read_decompile_write_and_reopen(tmp_path: Path) -> None:
    install_value = os.environ.get("GHIDRA_INSTALL_DIR")
    if not install_value:
        pytest.skip("GHIDRA_INSTALL_DIR 未配置")
    samples = (
        (FIXTURES / "libsymbolic.so", "fixture_symbolic"),
        (FIXTURES / "libstripped.so", "fixture_checksum"),
        (FIXTURES / "libcontrol_flow.so", "fixture_control_flow"),
    )
    if any(not sample.is_file() for sample, _ in samples):
        pytest.skip("先运行 scripts/build_fixtures.py")

    workspace = ProgramWorkspace(
        GhidraRuntime(Path(install_value)), project_location=tmp_path / "projects"
    )
    registry = build_default_registry(workspace)
    tools = {tool.name: tool.handler for tool in registry.enabled_tools()}

    for sample, expected_name in samples:
        opened = tools["program_open"](str(sample), analyze=True)
        program_id = opened["program_id"]
        info = tools["program_info"](program_id)
        assert "ELF" in info["format"]

        blocks = tools["memory_blocks_list"](program_id)
        assert blocks
        readable = next(block for block in blocks if block["initialized"])
        assert tools["memory_read"](program_id, readable["start"], 16)["length"] == 16

        functions = tools["functions_list"](program_id, offset=0, limit=1000)
        target = next(function for function in functions if function["name"] == expected_name)
        entry = target["entry_point"]
        assert tools["function_get"](program_id, entry)["entry_point"] == entry
        assert tools["instructions_list"](program_id, address=entry, limit=20)
        tools["symbols_list"](program_id, contains=expected_name, limit=20)
        tools["references_list"](program_id, entry, direction="both", limit=20)
        tools["strings_list"](program_id, limit=20)
        assert expected_name in tools["decompile_function"](program_id, entry, 60)["c"]
        tools["call_graph"](program_id, entry)
        graph = tools["control_flow_graph"](program_id, entry)
        assert graph["nodes"]
        data = tools["data_list"](program_id, limit=20)
        if data:
            assert tools["data_get"](program_id, data[0]["address"])["address"] == data[0]["address"]
        tools["variables_list"](program_id, entry)
        assert tools["pcode_list"](program_id, entry, limit=20)
        assert tools["data_types_list"](program_id, limit=20)
        tools["function_tags"](program_id, entry)
        tools["bookmarks_list"](program_id, limit=20)

        if expected_name == "fixture_symbolic":
            tools["function_rename"](program_id, entry, "verified_symbolic")
            tools["comment_set"](program_id, entry, "eol", "verified by integration test")
            assert any(item["address"] == entry for item in tools["comments_list"](program_id))
        tools["program_close"](program_id)

        if expected_name == "fixture_symbolic":
            reopened = tools["program_open"](str(sample), analyze=False)
            assert tools["function_get"](reopened["program_id"], entry)["name"] == "verified_symbolic"
            tools["program_close"](reopened["program_id"])

    workspace.close_all()
