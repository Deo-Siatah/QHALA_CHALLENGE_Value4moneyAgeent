import pytest

from agent.nodes import draft
from agent.nodes.draft import draft_node

SUMMARY = "Eighteen awards of classroom construction were compared, and one bid total sits 87.5% above the median of that pool."
FINDING = "One bid total is 87.5% above the median of eighteen similar awards, above the upper quartile of 5600000.0."
ANSWER = {
    "summary": SUMMARY,
    "bid_comments": {"Apex": "4.2% above the median, inside the normal range.",
                     "Bora": "87.5% above the median of eighteen similar awards."},
    "findings": [{"text": FINDING, "sources": ["a01", "a02"]}],
    "sources_used": ["a01", "a02"],
}


def award(award_id, value=4_000_000.0, title="Classroom block construction", year=2024):
    return {"award_id": award_id, "ocid": f"ocid-{award_id}", "data_year": year, "title": title,
            "buyer_name": "Ministry of Education", "category": "works", "value_kes": value,
            "currency": "KES", "quality_flags": []}


def benchmark(n=18):
    bids = [{"bidder": "Apex", "total": 5_000_000.0, "pct_vs_median": 4.2, "position": "within_range",
             "arithmetic_issues": []},
            {"bidder": "Bora", "total": 9_000_000.0, "pct_vs_median": 87.5, "position": "far_above",
             "arithmetic_issues": ["Stated total 9000000.00 does not match computed total 8400000.00"]}]
    return {"n": n, "confidence": "high", "median_kes": 4_800_000.0, "q1_kes": 4_100_000.0,
            "q3_kes": 5_600_000.0, "sources": [f"a{i:02d}" for i in range(1, n + 1)], "bids": bids}


def state(**overrides):
    base = {
        "run_id": "run-1", "tender_ref": "TENDER/NC/2026/014", "description": "construction of classroom blocks",
        "bids": [{"bidder": "Apex", "tender_ref": "TENDER/NC/2026/014", "currency": "KES", "items": [],
                  "stated_total": 5_000_000.0, "computed_total": 5_000_000.0, "arithmetic_ok": True,
                  "issues": []},
                 {"bidder": "Bora", "tender_ref": "TENDER/NC/2026/014", "currency": "KES", "items": [],
                  "stated_total": 9_000_000.0, "computed_total": 8_400_000.0, "arithmetic_ok": False,
                  "issues": ["Stated total 9000000.00 does not match computed total 8400000.00"]}],
        "benchmark": benchmark(),
        "pool": [award("a01"), award("a02", 5_000_000.0, "Classroom works", 2023), award("a03")],
        "excluded": {"different_work": 4, "no_value": 2},
        "search": {"match": "loose", "category": "works", "min_year": 2020, "attempts": 2},
        "verify_rounds": 0,
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def logged(audit_conn, monkeypatch):
    """Keep the audit wrapper off the real audit_log for every test in this module."""
    from mcp_server import audit
    from conftest import SharedConnection

    monkeypatch.setattr(audit, "get_conn", lambda: SharedConnection(audit_conn))


@pytest.fixture
def wording(monkeypatch):
    """Answer draft_review_wording with a canned review, capturing the payload."""
    calls = []

    def install(answer=ANSWER):
        def fake_ask(prompt_name, payload):
            calls.append((prompt_name, payload))
            return answer

        monkeypatch.setattr(draft, "ask_json", fake_ask)
        return calls

    return install


def test_the_payload_carries_the_benchmark_and_every_bid(wording):
    calls = wording()

    draft_node(state())

    name, payload = calls[0]
    assert name == "draft_review_wording"
    assert payload["tender_ref"] == "TENDER/NC/2026/014"
    assert payload["description"] == "construction of classroom blocks"
    assert payload["benchmark"] == benchmark()
    assert payload["excluded"] == {"different_work": 4, "no_value": 2}
    apex, bora = payload["bids"]
    assert apex == {"bidder": "Apex", "total": 5_000_000.0, "pct_vs_median": 4.2,
                    "position": "within_range", "arithmetic_issues": []}
    assert bora["arithmetic_issues"] == ["Stated total 9000000.00 does not match computed total 8400000.00"]
    assert [a["award_id"] for a in payload["awards"]] == ["a01", "a02", "a03"]


def test_the_award_payload_is_only_what_the_report_needs(wording):
    calls = wording()

    draft_node(state())

    assert calls[0][1]["awards"][0] == {"award_id": "a01", "title": "Classroom block construction",
                                        "value_kes": 4_000_000.0, "buyer_name": "Ministry of Education",
                                        "data_year": 2024}


def test_the_review_passes_the_search_echo_and_the_exclusions(wording):
    wording()

    result = draft_node(state())

    assert "## Comparison pool" in result["review_markdown"]
    assert "match=loose" in result["review_markdown"]
    assert "different_work (4)" in result["review_markdown"]


def test_the_sources_table_lists_exactly_the_cited_awards(wording):
    wording()

    result = draft_node(state())

    assert [s["award_id"] for s in result["sources"]] == ["a01", "a02"]
    assert result["sources"][0]["ocid"] == "ocid-a01"
    assert "a03" not in result["review_markdown"].split("## Sources")[1]


def test_a_cited_award_is_listed_once_even_when_two_findings_use_it(wording):
    wording(answer={**ANSWER, "findings": [{"text": FINDING, "sources": ["a01", "a02"]},
                                           {"text": "Two more similar awards exist.", "sources": ["a01", "a02"]}]})

    result = draft_node(state())

    assert [s["award_id"] for s in result["sources"]] == ["a01", "a02"]
    assert result["review_markdown"].count("| a01 |") == 1


def test_the_model_wording_lands_in_the_report(wording):
    wording()

    result = draft_node(state())

    assert result["summary"] == SUMMARY
    assert result["findings"][0]["text"] == FINDING
    assert "87.5% above the median" in result["review_markdown"]
    assert "does not recommend an award" in result["review_markdown"]


def test_a_second_draft_replaces_the_findings_instead_of_adding_to_them(wording):
    wording()
    first = draft_node(state())
    wording(answer={**ANSWER, "findings": [{"text": "A different finding.", "sources": ["a03"]}]})

    second = draft_node(state(**{**first, "verify_rounds": 1}))

    assert [f["text"] for f in second["findings"]] == ["A different finding."]
    assert second["verify_rounds"] == 2
    assert "A different finding." in second["review_markdown"]
    assert FINDING not in second["review_markdown"]


def test_verify_rounds_counts_every_draft(wording):
    wording()

    result = draft_node(state(verify_rounds=1))

    assert result["verify_rounds"] == 2


def test_a_rejected_wording_is_recorded_and_no_report_is_written(wording):
    wording(answer={**ANSWER, "findings": [{"text": "The cheapest bidder is the winner.", "sources": ["a01"]}]})

    result = draft_node(state())

    assert result["review_markdown"] == ""
    assert "winner" in result["errors"][0]
    assert "draft_review_file" in result["errors"][0]


def test_a_rejected_wording_leaves_the_earlier_report_alone(wording):
    wording()
    first = draft_node(state())
    wording(answer={**ANSWER, "findings": [{"text": "No sources here.", "sources": []}]})

    second = draft_node(state(**{**first, "verify_rounds": 1}))

    assert second["review_markdown"] == ""
    assert "errors" in second
    assert second["verify_rounds"] == 2


def test_a_model_citing_an_award_that_was_never_in_the_pool_is_refused(wording):
    wording(answer={**ANSWER, "findings": [{"text": FINDING, "sources": ["a99"]}]})

    result = draft_node(state())

    assert result["review_markdown"] == ""
    assert "a99" in result["errors"][0]
    assert result["sources"] == []


def test_a_committee_file_comes_out_with_its_fixed_sections(wording):
    wording()

    result = draft_node(state())

    markdown = result["review_markdown"]
    assert markdown.startswith("# Price review evidence: TENDER/NC/2026/014")
    assert "## Summary" in markdown
    assert "## Comparison pool" in markdown
    assert "## Bids" in markdown
    assert "## Findings" in markdown
    assert "## Limitations" in markdown
    assert "## Sources" in markdown
    assert "Sources: a01, a02" in markdown


def test_the_bid_table_shows_the_total_the_percentage_and_the_position(wording):
    wording()

    result = draft_node(state())

    bids_section = result["review_markdown"].split("## Bids")[1].split("## Findings")[0]
    assert "9,000,000.00" in bids_section
    assert "87.5%" in bids_section
    assert "far_above" in bids_section
    assert "87.5% above the median of eighteen similar awards." in bids_section


def test_the_draft_call_is_logged_under_the_run(wording, audit_conn):
    wording()

    draft_node(state())

    rows = audit_conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    assert [r["tool"] for r in rows] == ["draft_review_file"]
    assert rows[0]["run_id"] == "run-1"
    assert rows[0]["input"]["review"]["tender_ref"] == "TENDER/NC/2026/014"
    assert rows[0]["output"]["markdown"].startswith("# Price review evidence")
