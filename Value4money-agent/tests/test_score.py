import pytest

from agent.nodes import score
from agent.nodes.score import score_node
from config import settings


def bid(bidder, stated_total, computed_total=None, issues=None, ok=True):
    return {"bidder": bidder, "tender_ref": "T/1", "currency": "KES", "items": [],
            "stated_total": stated_total, "computed_total": computed_total if computed_total
            is not None else stated_total, "arithmetic_ok": ok, "issues": issues or []}


def pool(n, start=1):
    return [{"award_id": f"a{i:02d}", "value_kes": float(i * 1_000_000)} for i in range(start, start + n)]


@pytest.fixture(autouse=True)
def logged(audit_conn, monkeypatch):
    """Keep the audit wrapper off the real audit_log for every test in this module."""
    from mcp_server import audit
    from conftest import SharedConnection

    monkeypatch.setattr(audit, "get_conn", lambda: SharedConnection(audit_conn))


def run(bids, pool_rows, **overrides):
    state = {"run_id": "run-1", "bids": bids, "pool": pool_rows}
    state.update(overrides)
    return score_node(state)


def test_the_stated_totals_are_benchmarked_against_the_pool():
    result = run([bid("Apex", 3_500_000.0), bid("Bora", 9_000_000.0)], pool(7))

    assert result["benchmark"]["n"] == 7
    assert [b["bidder"] for b in result["benchmark"]["bids"]] == ["Apex", "Bora"]
    assert result["benchmark"]["median_kes"] == 4_000_000.0
    assert result["benchmark"]["bids"][0]["total"] == 3_500_000.0


def test_the_result_is_stored_untouched():
    result = run([bid("Apex", 3_500_000.0)], pool(7))

    assert result["benchmark"]["confidence"] == "medium"
    assert result["benchmark"]["q1_kes"] == 2_500_000.0
    assert result["benchmark"]["q3_kes"] == 5_500_000.0
    assert result["benchmark"]["sources"] == [f"a{i:02d}" for i in range(1, 8)]


def test_a_bid_whose_arithmetic_failed_is_benchmarked_on_its_stated_total():
    bids = [bid("Apex", 9_000_000.0, computed_total=8_400_000.0, ok=False,
                issues=["Stated total 9000000.00 does not match computed total 8400000.00"])]

    result = run(bids, pool(7))

    assert result["benchmark"]["bids"][0]["total"] == 9_000_000.0
    assert result["benchmark"]["bids"][0]["pct_vs_median"] == 125.0


def test_an_empty_pool_gives_insufficient_rather_than_an_error():
    result = run([bid("Apex", 3_500_000.0)], [])

    assert result["benchmark"]["n"] == 0
    assert result["benchmark"]["confidence"] == "insufficient"
    assert result["benchmark"]["median_kes"] is None
    assert result["benchmark"]["bids"][0]["position"] is None


def test_a_thin_pool_is_scored_with_low_confidence():
    result = run([bid("Apex", 3_000_000.0)], pool(settings.min_comparables))

    assert result["benchmark"]["confidence"] == "medium"
    assert result["benchmark"]["bids"][0]["position"] == "within_range"


def test_no_node_field_is_touched_beyond_the_benchmark():
    bids = [bid("Apex", 3_500_000.0)]

    result = run(bids, pool(7), pool_size=7, quality={"pool_size": 9}, errors=["earlier problem"])

    assert set(result) == {"benchmark"}
    assert result["benchmark"]["n"] == 7


def test_bid_order_is_kept():
    bids = [bid("Zed", 1_000_000.0), bid("Apex", 3_500_000.0), bid("Bora", 9_000_000.0)]

    result = run(bids, pool(7))

    assert [b["bidder"] for b in result["benchmark"]["bids"]] == ["Zed", "Apex", "Bora"]


def test_the_benchmark_call_is_logged_under_the_run(audit_conn):
    run([bid("Apex", 3_500_000.0)], pool(7))

    rows = audit_conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    assert len(rows) == 1
    assert rows[0]["tool"] == "benchmark_price"
    assert rows[0]["run_id"] == "run-1"
    assert rows[0]["input"]["bids"] == [{"bidder": "Apex", "total": 3_500_000.0}]
    assert rows[0]["input"]["pool"] == pool(7)


def test_quality_check_then_score_run_end_to_end_on_real_tools(monkeypatch, audit_conn):
    from agent.nodes import quality_check
    from agent.nodes.quality_check import quality_check_node
    from agent.tools import benchmark_price

    def fake_ask(prompt_name, payload):
        if prompt_name == "quality_similarity_judgement":
            return {"judgements": {a["award_id"]: {"verdict": "same_work", "reason": "classroom blocks"}
                                   for a in payload["awards"]}}
        return {"verdicts": {a["award_id"]: {"verdict": "keep", "reason": "real multi-site programme"}
                             for a in payload["awards"]}}

    monkeypatch.setattr(quality_check, "ask_json", fake_ask)
    monkeypatch.setattr(score, "benchmark_price", benchmark_price)

    candidates = [dict(row, title="Classroom block construction", buyer_name="Ministry of Education",
                       data_year=2024, currency="KES")
                  for row in pool(settings.good_pool_n)]
    candidates.append({"award_id": "a90", "value_kes": 400_000_000.0, "currency": "KES",
                       "title": "Classroom works", "buyer_name": "County Government",
                       "data_year": 2023})

    state = quality_check_node({"run_id": "run-e2e", "description": "construction of classroom blocks",
                                "candidates": candidates, "quality_attempts": 0})
    result = score_node({"run_id": "run-e2e", "bids": [bid("Apex", 5_000_000.0)], **state})

    benchmark = result["benchmark"]
    assert state["pool_size"] == settings.good_pool_n + 1
    assert benchmark["n"] == settings.good_pool_n + 1
    assert benchmark["confidence"] == "medium"
    assert benchmark["median_kes"] == 6_000_000.0
    assert benchmark["bids"][0]["pct_vs_median"] == -16.7
    assert "a90" in benchmark["sources"]
