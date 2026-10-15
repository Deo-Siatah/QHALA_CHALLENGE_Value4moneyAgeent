import asyncio

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from mcp_server import audit, server
from conftest import SharedConnection

TOOLS = ["parse_bid_pdf", "find_comparable_awards", "flag_data_quality", "benchmark_price",
         "draft_review_file", "submit_for_committee"]


def registered(mcp_server):
    """The tools the server exposes, by name."""
    return {tool.name: tool for tool in asyncio.run(mcp_server.list_tools())}


def test_exactly_the_six_own_tools_are_registered():
    assert set(registered(server.mcp)) == set(TOOLS)


@pytest.mark.parametrize("name", TOOLS)
def test_every_tool_schema_carries_run_id(name):
    schema = registered(server.mcp)[name].inputSchema

    assert "run_id" in schema.get("properties", {})
    assert schema["properties"]["run_id"]["type"] == "string"
    assert "run_id" in schema.get("required", [])


def test_a_call_through_the_server_writes_one_audit_row(audit_conn, monkeypatch):
    monkeypatch.setattr(audit, "get_conn", lambda: SharedConnection(audit_conn))
    pool = [{"award_id": f"a{i:02d}", "value_kes": float(i * 1_000_000)} for i in range(1, 8)]
    bids = [{"bidder": "Apex", "total": 3_500_000.0}]

    result = asyncio.run(server.mcp.call_tool("benchmark_price",
                                              {"run_id": "run-1", "bids": bids, "pool": pool}))

    assert result[1]["result"]["n"] == 7
    rows = audit_conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    assert len(rows) == 1
    assert rows[0]["run_id"] == "run-1"
    assert rows[0]["tool"] == "benchmark_price"
    assert rows[0]["actor"] == "agent"
    assert rows[0]["input"] == {"bids": bids, "pool": pool}
    assert rows[0]["output"]["n"] == 7
    assert rows[0]["approved_by"] is None


def test_a_refused_tool_still_leaves_an_audit_row(audit_conn, monkeypatch):
    monkeypatch.setattr(audit, "get_conn", lambda: SharedConnection(audit_conn))

    with pytest.raises(ToolError):
        asyncio.run(server.mcp.call_tool("benchmark_price", {"run_id": "run-2", "bids": [], "pool": []}))

    rows = audit_conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    assert len(rows) == 1
    assert rows[0]["run_id"] == "run-2"
    assert "error" in rows[0]["output"]
    assert "bids" in rows[0]["output"]["error"]
