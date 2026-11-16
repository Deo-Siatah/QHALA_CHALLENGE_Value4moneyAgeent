import pytest

from agent.llm import LlmError
from agent.nodes import draft
from agent.nodes.draft import draft_node

NOTES = {
    "summary_note": "The pool is small, so the figures are context rather than proof.",
    "finding_notes": {
        "pool": "The awards cover similar classroom work.",
        "bid:2": "The scope should be checked before relying on this comparison.",
        "arithmetic:3": "The bid document should be checked against its line items.",
    },
}


def award(award_id, value=4_000_000.0, title="Classroom block construction", year=2024):
    return {"award_id": award_id, "ocid": f"ocid-{award_id}", "data_year": year, "title": title,
            "buyer_name": "Ministry of Education", "category": "works", "value_kes": value,
            "currency": "KES", "quality_flags": []}


def benchmark(n=11):
    return {"n": n, "confidence": "medium", "median_kes": 2_839_845.72,
            "q1_kes": 1_956_829.0, "q3_kes": 3_494_974.74,
            "sources": ["a01", "a02", "a03"],
            "bids": [{"bidder": "Apex", "total": 3_150_000.0, "pct_vs_median": 10.9,
                      "position": "within_range"},
                     {"bidder": "Bora", "total": 8_650_000.0, "pct_vs_median": 204.6,
                      "position": "far_above"},
                     {"bidder": "Zed", "total": 2_750_000.0, "pct_vs_median": -3.2,
                      "position": "within_range"}]}


def state(**overrides):
    base = {
        "run_id": "run-1", "tender_ref": "TENDER/NC/2026/014",
        "description": "construction of classroom blocks",
        "bids": [{"bidder": "Apex", "file": "apex.pdf", "total_page": 2,
                  "tender_ref": "TENDER/NC/2026/014", "currency": "KES", "items": [],
                  "stated_total": 3_150_000.0, "computed_total": 3_150_000.0,
                  "arithmetic_ok": True, "status": "ok", "issues": []},
                 {"bidder": "Bora", "file": "bora.pdf", "total_page": 3,
                  "tender_ref": "TENDER/NC/2026/014", "currency": "KES", "items": [],
                  "stated_total": 8_650_000.0, "computed_total": 8_650_000.0,
                  "arithmetic_ok": True, "status": "ok", "issues": []},
                 {"bidder": "Zed", "file": "zed.pdf", "total_page": 1,
                  "tender_ref": "TENDER/NC/2026/014", "currency": "KES", "items": [],
                  "stated_total": 2_750_000.0, "computed_total": 2_690_000.0,
                  "arithmetic_ok": False, "status": "ok",
                  "issues": ["Stated total 2750000.00 does not match computed total 2690000.00"]}],
        "benchmark": benchmark(),
        "pool": [award("a01", 2_501_490.0), award("a02", 3_289_999.48, "Classroom works", 2023),
                 award("a03", 2_839_845.72)],
        "excluded": {"different_work": 4, "no_value": 2},
        "search": {"match": "loose", "category": "works", "min_year": 2020, "attempts": 2},
        "verify_rounds": 0,
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def logged(audit_conn, monkeypatch):
    from mcp_server import audit
    from conftest import SharedConnection

    monkeypatch.setattr(audit, "get_conn", lambda: SharedConnection(audit_conn))


@pytest.fixture
def wording(monkeypatch):
    calls = []

    def install(answer=NOTES, raises=None):
        def fake_ask(prompt_name, payload):
            calls.append((prompt_name, payload))
            if raises is not None:
                raise raises
            return answer

        monkeypatch.setattr(draft, "ask_json", fake_ask)
        return calls

    return install


def test_the_model_sees_the_findings_but_not_the_figures(wording):
    calls = wording()

    draft_node(state())

    name, payload = calls[0]
    assert name == "draft_review_wording"
    assert payload["tender_ref"] == "TENDER/NC/2026/014"
    assert payload["pool_size"] == 3
    assert [finding["key"] for finding in payload["findings"]] == ["pool", "bid:2", "arithmetic:3"]
    assert "median" not in str(payload)
    assert "KES" not in str(payload)


def test_code_builds_typed_pool_and_bid_findings(wording):
    wording()

    result = draft_node(state())

    assert {bid["bidder"] for bid in result["report_model"]["bids"]} == {"Apex", "Bora", "Zed"}
    assert result["report_model"]["benchmark"]["median"] == 2_839_845.72
    assert result["report_model"]["annex_pool"][0]["award_id"] == "a01"

    pool_finding, bid_finding, arithmetic = result["findings"]
    assert pool_finding["kind"] == "pool"
    assert "2,839,845.72" not in pool_finding["sources"][0]
    assert pool_finding["sources"] == [
        {"kind": "pool", "award_id": "a01"},
        {"kind": "pool", "award_id": "a02"},
        {"kind": "pool", "award_id": "a03"},
    ]
    assert bid_finding["kind"] == "bid"
    assert bid_finding["sources"][0] == {"kind": "bid", "bidder": "Bora",
                                         "file": "bora.pdf", "page": 3}
    assert arithmetic["sources"] == [{"kind": "bid", "bidder": "Zed",
                                      "file": "zed.pdf", "page": 1}]


def test_the_bid_finding_cites_the_bid_and_the_whole_pool(wording):
    wording()

    result = draft_node(state())

    bid_finding = result["findings"][1]
    assert [source.get("award_id") for source in bid_finding["sources"][1:]] == [
        "a01", "a02", "a03"]
    assert "205% above" in bid_finding["text"]
    assert "far above the upper quartile" in bid_finding["text"]


def test_the_arithmetic_finding_computes_the_difference_from_the_two_totals(wording):
    wording()

    result = draft_node(state())

    arithmetic = result["findings"][2]
    assert "KES 2,750,000.00" in arithmetic["text"]
    assert "KES 2,690,000.00" in arithmetic["text"]
    assert "KES 60,000.00" in arithmetic["text"]


def test_model_notes_are_appended_but_never_become_figures(wording):
    wording()

    result = draft_node(state())

    assert "The pool is small" in result["summary"]
    assert "The scope should be checked" in result["findings"][1]["text"]
    assert result["summary_note"] == NOTES["summary_note"]
    assert result["finding_notes"] == NOTES["finding_notes"]


def test_a_note_with_a_figure_is_refused_and_no_report_is_written(wording):
    bad = {"summary_note": "Eleven awards were compared.", "finding_notes": {}}
    wording(answer=bad)

    result = draft_node(state())

    assert result["review_markdown"] == ""
    assert "summary note" in result["errors"][0]
    assert result["verify_rounds"] == 1


def test_the_final_attempt_renders_without_notes_instead_of_failing(wording):
    wording(raises=LlmError("groq timed out"))

    result = draft_node(state(verify_rounds=1))

    assert result["report_degraded"] is True
    assert result["review_markdown"].startswith("# Price review evidence")
    assert "## Method" in result["review_markdown"]


def test_the_sources_table_lists_every_pool_award(wording):
    wording()

    result = draft_node(state())

    assert [source["award_id"] for source in result["sources"]] == ["a01", "a02", "a03"]
    assert result["review_markdown"].count("| a01 |") == 1


def test_the_report_has_no_old_number_defects(wording):
    wording()

    markdown = draft_node(state())["review_markdown"]

    assert "Twenty" not in markdown
    assert "twenty-five" not in markdown
    assert "?KES" not in markdown
    assert "-3% below" not in markdown
    assert "3% below" in markdown


def test_the_classroom_fixture_defects_stay_fixed(wording):
    wording(answer={"summary_note": "The pool rests on similar classroom work.",
                    "finding_notes": {
                        "pool": "The comparison rests on similar classroom work.",
                        "bid:1": "The total is well below the normal range.",
                        "arithmetic:2": "The stated total and the line items disagree."}})
    fixture = state(
        benchmark={"n": 25, "confidence": "high", "median_kes": 2_373_706.18,
                   "q1_kes": 1_999_310.0, "q3_kes": 3_587_126.0,
                   "bids": [{"bidder": "Karuru Works Agency Ltd", "total": 1_228_000.0,
                             "pct_vs_median": -48.3, "position": "below_range"},
                            {"bidder": "Nyando Enterprises Ltd", "total": 2_833_600.0,
                             "pct_vs_median": 19.4, "position": "within_range"}]},
        bids=[{"bidder": "Karuru Works Agency Ltd", "file": "karuru.pdf", "total_page": 2,
               "stated_total": 1_228_000.0, "computed_total": 1_228_000.0,
               "arithmetic_ok": True, "status": "ok", "issues": []},
              {"bidder": "Nyando Enterprises Ltd", "file": "nyando.pdf", "total_page": 3,
               "stated_total": 2_833_600.0, "computed_total": 2_683_600.0,
               "arithmetic_ok": False, "status": "ok",
               "issues": ["Stated total 2833600.00 does not match computed total 2683600.00"]}],
        pool=[award("20260309112625-155041", 2_373_706.18),
              award("20260408125751-156392", 3_587_126.0),
              award("20240214131435-72591", 1_999_310.0)],
        excluded={"different_work": 4, "scale_mismatch": 1})

    markdown = draft_node(fixture)["review_markdown"]

    assert "KES 2,373,706.18" in markdown
    assert "2373706.18 KES" not in markdown
    assert "48% below" in markdown
    assert "48.3% below" not in markdown
    assert "Twenty" not in markdown
    assert "twenty-five" not in markdown
    assert "Nyando Enterprises Ltd, nyando.pdf p.3" in markdown
    assert "different work (4)" in markdown
    assert "scale_mismatch" not in markdown


def test_same_input_writes_the_same_file(wording):
    wording()

    first = draft_node(state())["review_markdown"]
    second = draft_node(state())["review_markdown"]

    assert first == second


def test_a_committee_file_comes_out_with_its_fixed_sections(wording):
    wording()

    markdown = draft_node(state())["review_markdown"]

    assert markdown.startswith("# Price review evidence: TENDER/NC/2026/014")
    for heading in ("## Bottom line", "## Bids", "## Method",
                    "## Annex: comparable awards"):
        assert heading in markdown
    for award_id in ("a01", "a02", "a03"):
        assert award_id in markdown


def test_the_bid_table_shows_the_total_the_percentage_and_the_position(wording):
    wording()

    markdown = draft_node(state())["review_markdown"]
    bids_section = markdown.split("## Bids")[1].split("## Method")[0]

    assert "8,650,000.00" in bids_section
    assert "205% above" in bids_section
    assert "far above the usual price" in bids_section


def test_verify_rounds_counts_every_draft(wording):
    wording()

    result = draft_node(state(verify_rounds=1))

    assert result["verify_rounds"] == 2


def test_the_draft_call_is_logged_under_the_run(wording, audit_conn):
    wording()

    draft_node(state())

    rows = audit_conn.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
    assert [r["tool"] for r in rows] == ["draft_review_file"]
    assert rows[0]["run_id"] == "run-1"
    assert rows[0]["input"]["review"]["tender_ref"] == "TENDER/NC/2026/014"
