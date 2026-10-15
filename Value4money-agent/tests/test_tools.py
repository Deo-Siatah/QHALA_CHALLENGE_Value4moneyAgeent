import pytest
from datetime import datetime, timezone

from mcp_server import audit
from mcp_server.tools import submit_for_committee as submit_tool
from agent import tools
from agent.tools import (parse_bid_pdf, find_comparable_awards, flag_data_quality,
                              benchmark_price, draft_review_file, submit_for_committee)
from conftest import SharedConnection

BID_PDF_LINES = [
    "Bidder: Apex",
    "Tender reference: TENDER/NC/2026/014",
    "Currency: KES",
    "1 | Classroom construction | item | 10 | 100000 | 1000000",
    "Stated total: 1000000",
]


@pytest.fixture
def rows(audit_conn, monkeypatch):
    """Point the audit wrapper at the temporary audit_log table and read back its rows."""
    monkeypatch.setattr(audit, "get_conn", lambda: SharedConnection(audit_conn))

    def read(run_id="run-1"):
        return audit_conn.execute(
            "SELECT * FROM audit_log WHERE run_id = %s ORDER BY id", (run_id,)).fetchall()

    return read


@pytest.fixture
def bid_pdf(tmp_path, monkeypatch):
    """A one page bid PDF in tmp_path, built with fpdf2 as the test rules require."""
    from conftest import make_pdf
    monkeypatch.setattr(tools.settings, "bids_dir", tmp_path)
    return make_pdf(tmp_path, "apex.pdf", BID_PDF_LINES)


def test_parse_bid_pdf_forwards_the_path_and_logs_one_row(rows, bid_pdf):
    result = parse_bid_pdf("run-1", str(bid_pdf))

    assert result["bidder"] == "Apex"
    assert result["tender_ref"] == "TENDER/NC/2026/014"
    assert result["stated_total"] == 1000000.0
    assert result["arithmetic_ok"] is True
    logged = rows()
    assert len(logged) == 1
    assert logged[0]["tool"] == "parse_bid_pdf"
    assert logged[0]["input"] == {"path": str(bid_pdf)}
    assert logged[0]["output"]["bidder"] == "Apex"
    assert logged[0]["approved_by"] is None


def test_a_missing_run_id_is_refused_before_the_tool_runs(rows, bid_pdf):
    with pytest.raises(audit.AuditError):
        parse_bid_pdf("", str(bid_pdf))

    assert rows("") == []


def test_a_failed_tool_call_still_leaves_a_row(rows):
    with pytest.raises(ValueError):
        find_comparable_awards("run-1", "classroom construction", category="wrong")

    logged = rows()
    assert len(logged) == 1
    assert logged[0]["tool"] == "find_comparable_awards"
    assert "error" in logged[0]["output"]


def test_find_comparable_awards_forwards_every_argument(rows, monkeypatch):
    seen = {}

    def fake(query, category, buyer_id, match, min_year, exclude_ocid):
        seen.update({"query": query, "category": category, "buyer_id": buyer_id, "match": match,
                     "min_year": min_year, "exclude_ocid": exclude_ocid})
        return {"filters": {}, "count": 0, "candidates": []}

    monkeypatch.setattr(tools, "_find_comparable_awards", fake)

    find_comparable_awards("run-1", "classroom construction", category="works", buyer_id="buyer-7",
                           match="loose", min_year=2023, exclude_ocid="ocid-1")

    assert seen == {"query": "classroom construction", "category": "works", "buyer_id": "buyer-7",
                    "match": "loose", "min_year": 2023, "exclude_ocid": "ocid-1"}
    assert rows()[0]["input"] == {"query": "classroom construction", "category": "works",
                                  "buyer_id": "buyer-7", "match": "loose", "min_year": 2023,
                                  "exclude_ocid": "ocid-1"}


def test_the_defaults_are_left_to_the_tool_and_not_logged_as_arguments(rows, monkeypatch):
    monkeypatch.setattr(tools, "_find_comparable_awards",
                        lambda *args: {"filters": {}, "count": 0, "candidates": []})

    find_comparable_awards("run-1", "road works")

    assert rows()[0]["input"] == {"query": "road works"}


def test_flag_data_quality_returns_the_tool_result(rows):
    candidates = [{"award_id": "a1", "value_kes": 1000000.0, "currency": "KES"},
                  {"award_id": "a2", "value_kes": 0.0, "currency": "KES"}]

    result = flag_data_quality("run-1", candidates)

    assert result["pool_size"] == 1
    assert result["counts"]["excluded"] == 1
    assert rows()[0]["tool"] == "flag_data_quality"
    assert rows()[0]["input"] == {"candidates": candidates}


def test_benchmark_price_returns_the_statistics(rows):
    pool = [{"award_id": f"a{i:02d}", "value_kes": float(i * 1_000_000)} for i in range(1, 8)]
    bids = [{"bidder": "Apex", "total": 3_500_000.0}]

    result = benchmark_price("run-1", bids, pool)

    assert result["n"] == 7
    assert result["bids"][0]["position"] == "within_range"
    assert rows()[0]["tool"] == "benchmark_price"
    assert rows()[0]["output"]["median_kes"] == 4_000_000.0


def test_draft_review_file_returns_markdown(rows):
    review = {
        "run_id": "run-1",
        "tender_ref": "TENDER/NC/2026/014",
        "summary": "One pool of awards of the same kind of work.",
        "benchmark": {"n": 6, "confidence": "high", "median_kes": 3_000_000.0,
                      "q1_kes": 2_000_000.0, "q3_kes": 4_000_000.0, "sources": ["a01"],
                      "bids": [{"bidder": "Apex", "total": 3_000_000.0, "pct_vs_median": 0.0,
                                "position": "within_range"}]},
        "search": {"match": "strict", "category": "works", "min_year": 2023, "attempts": 1},
        "excluded": {"no_value": 1},
        "bids": [{"bidder": "Apex", "arithmetic_issues": [], "comment": "On the median."}],
        "findings": [{"text": "Six similar awards sit between 2,000,000 and 4,000,000 KES.",
                      "sources": ["a01"]}],
        "sources": [{"award_id": "a01", "ocid": "ocid-001", "data_year": 2024,
                     "buyer_name": "Ministry of Education", "title": "Classroom construction",
                     "value_kes": 3_000_000.0}],
    }

    result = draft_review_file("run-1", review)

    assert "## Comparison pool" in result["markdown"]
    assert rows()[0]["tool"] == "draft_review_file"
    assert rows()[0]["output"] == result


def test_submit_for_committee_records_the_approver(audit_conn, reports_conn, tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "get_conn", lambda: SharedConnection(audit_conn))
    monkeypatch.setattr(tools.settings, "outputs_dir", tmp_path)
    monkeypatch.setattr(submit_tool, "get_conn", lambda: SharedConnection(reports_conn))

    result = submit_for_committee("run-1", "# Report\n", "Grace Wanjiku")

    assert result["approved_by"] == "Grace Wanjiku"
    assert (tmp_path / "reports" / "run-1.md").read_text(encoding="utf-8") == "# Report\n"
    logged = audit_conn.execute(
        "SELECT * FROM audit_log WHERE run_id = %s ORDER BY id", ("run-1",)).fetchall()
    assert len(logged) == 1
    assert logged[0]["tool"] == "submit_for_committee"
    assert logged[0]["approved_by"] == "Grace Wanjiku"
    assert logged[0]["output"]["report_id"] == result["report_id"]


def test_submit_for_committee_refuses_a_placeholder_approver(audit_conn, reports_conn, tmp_path,
                                                             monkeypatch):
    monkeypatch.setattr(audit, "get_conn", lambda: SharedConnection(audit_conn))
    monkeypatch.setattr(tools.settings, "outputs_dir", tmp_path)
    monkeypatch.setattr(submit_tool, "get_conn", lambda: SharedConnection(reports_conn))

    with pytest.raises(ValueError):
        submit_for_committee("run-1", "# Report\n", "agent")

    assert reports_conn.execute("SELECT count(*) AS n FROM reports").fetchone()["n"] == 0
    assert not (tmp_path / "reports").exists()
    logged = audit_conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    assert len(logged) == 1
    assert "error" in logged[0]["output"]


def test_the_client_surface_matches_the_mcp_surface():
    from mcp_server import server

    for name in ["parse_bid_pdf", "find_comparable_awards", "flag_data_quality", "benchmark_price",
                 "draft_review_file", "submit_for_committee"]:
        client_params = list(getattr(tools, name).__annotations__)
        server_params = list(getattr(server, f"{name}_tool").__annotations__)
        assert client_params == server_params, name
