import pytest

from agent.nodes.verify_sources import verify_sources_node

NOT_ENOUGH = "Not enough comparable awards to benchmark these bids."

POOL_NOTE = "The awards cover similar classroom work."
BID_NOTE = "The scope should be checked against the tender."


@pytest.fixture(autouse=True)
def logged(audit_conn, monkeypatch):
    """Keep the audit wrapper off the real audit_log for every test in this module."""
    from mcp_server import audit
    from conftest import SharedConnection

    monkeypatch.setattr(audit, "get_conn", lambda: SharedConnection(audit_conn))


def award(award_id, value=4_000_000.0, year=2024):
    return {"award_id": award_id, "ocid": f"ocid-{award_id}", "data_year": year,
            "title": "Classroom block construction", "buyer_name": "Ministry of Education",
            "value_kes": value, "category": "works", "currency": "KES", "quality_flags": []}


def pool_sources():
    return [{"kind": "pool", "award_id": "a01"}, {"kind": "pool", "award_id": "a02"},
            {"kind": "pool", "award_id": "a03"}]


def clean_findings():
    return [
        {"key": "pool", "kind": "pool", "text":
         "3 comparable awards have a median of KES 4,000,000.00 and a normal range of "
         "KES 3,000,000.00 to KES 5,000,000.00.", "sources": pool_sources(),
         "note": POOL_NOTE},
        {"key": "bid:2", "kind": "bid", "text":
         "Bora total KES 9,000,000.00 is 88% above the median of 3 similar awards, "
         "far above the upper quartile.", "sources": [
             {"kind": "bid", "bidder": "Bora", "file": "bora.pdf", "page": 2},
             {"kind": "pool", "award_id": "a01"}, {"kind": "pool", "award_id": "a02"},
             {"kind": "pool", "award_id": "a03"}], "note": BID_NOTE},
    ]


def state(**overrides):
    base = {
        "run_id": "run-1", "tender_ref": "TENDER/NC/2026/014",
        "description": "construction of classroom blocks",
        "benchmark": {"n": 3, "confidence": "medium", "median_kes": 4_000_000.0,
                      "q1_kes": 3_000_000.0, "q3_kes": 5_000_000.0,
                      "sources": ["a01", "a02", "a03"],
                      "bids": [{"bidder": "Apex", "total": 5_000_000.0, "pct_vs_median": 25.0,
                                "position": "within_range"},
                               {"bidder": "Bora", "total": 9_000_000.0, "pct_vs_median": 125.0,
                                "position": "far_above"}]},
        "pool": [award("a01"), award("a02", 5_000_000.0), award("a03", 3_000_000.0, 2023)],
        "bids": [{"bidder": "Apex", "file": "apex.pdf", "total_page": 1,
                  "tender_ref": "TENDER/NC/2026/014", "currency": "KES", "items": [],
                  "stated_total": 5_000_000.0, "computed_total": 5_000_000.0,
                  "arithmetic_ok": True, "status": "ok", "issues": []},
                 {"bidder": "Bora", "file": "bora.pdf", "total_page": 2,
                  "tender_ref": "TENDER/NC/2026/014", "currency": "KES", "items": [],
                  "stated_total": 9_000_000.0, "computed_total": 9_000_000.0,
                  "arithmetic_ok": True, "status": "ok", "issues": []}],
        "summary": POOL_NOTE,
        "summary_note": POOL_NOTE,
        "finding_notes": {"pool": POOL_NOTE, "bid:2": BID_NOTE},
        "report_degraded": False,
        "findings": clean_findings(),
        "sources": [{"award_id": "a01", "ocid": "ocid-a01", "data_year": 2024,
                     "buyer_name": "Ministry of Education", "title": "Classroom block construction",
                     "value_kes": 4_000_000.0},
                    {"award_id": "a02", "ocid": "ocid-a02", "data_year": 2024,
                     "buyer_name": "Ministry of Education", "title": "Classroom works",
                     "value_kes": 5_000_000.0},
                    {"award_id": "a03", "ocid": "ocid-a03", "data_year": 2023,
                     "buyer_name": "County Government", "title": "Classroom works",
                     "value_kes": 3_000_000.0}],
        "review_markdown": "# Price review evidence: TENDER/NC/2026/014\n\n## Findings\n",
        "excluded": {"different_work": 1},
    }
    base.update(overrides)
    return base


def failures(**overrides):
    return verify_sources_node(state(**overrides))["verify_failures"]


def test_a_clean_draft_verifies():
    result = verify_sources_node(state())

    assert result["verify_ok"] is True
    assert result["verify_failures"] == []


def test_a_missing_report_fails():
    result = verify_sources_node(state(review_markdown=""))

    assert result["verify_ok"] is False
    assert "no review to verify" in result["verify_failures"][0]


def test_a_finding_without_a_source_fails():
    result = verify_sources_node(state(findings=[{"text": "Something is off.", "sources": []}]))

    assert result["verify_ok"] is False
    assert any("finding 1" in failure and "no source" in failure
               for failure in result["verify_failures"])


def test_a_finding_citing_an_award_that_is_not_in_the_sources_fails():
    result = verify_sources_node(state(findings=clean_findings() + [
        {"kind": "pool", "text": "An extra award.", "sources": [{"kind": "pool", "award_id": "a99"}]}]))

    assert result["verify_ok"] is False
    assert any("a99" in failure for failure in result["verify_failures"])


def test_a_finding_citing_an_award_outside_the_benchmarked_pool_fails():
    listed = state()["sources"] + [{"award_id": "a04", "ocid": "ocid-a04", "data_year": 2024,
                                    "buyer_name": "County Government", "title": "Classroom works",
                                    "value_kes": 4_500_000.0}]

    result = verify_sources_node(state(
        findings=clean_findings() + [{"kind": "pool", "text": "An extra award.",
                                      "sources": [{"kind": "pool", "award_id": "a04"}]}],
        sources=listed))

    assert result["verify_ok"] is False
    assert any("a04" in failure for failure in result["verify_failures"])


def test_a_bid_source_needs_the_bid_file_and_page_that_exist():
    findings = clean_findings()
    findings[1]["sources"][0]["file"] = "other.pdf"

    result = verify_sources_node(state(findings=findings))

    assert result["verify_ok"] is False
    assert any("other.pdf" in failure for failure in result["verify_failures"])


def test_a_bid_source_page_must_be_inside_the_document():
    findings = clean_findings()
    findings[1]["sources"][0]["page"] = 9

    result = verify_sources_node(state(findings=findings))

    assert result["verify_ok"] is False
    assert any("page 9" in failure or "p.9" in failure for failure in result["verify_failures"])


def test_every_pooled_award_must_be_cited_by_a_finding():
    findings = clean_findings()
    findings[0]["sources"] = findings[0]["sources"][:2]
    findings[1]["sources"] = [source for source in findings[1]["sources"]
                              if source.get("award_id") != "a03"]

    result = verify_sources_node(state(findings=findings))

    assert result["verify_ok"] is False
    assert any("a03" in failure for failure in result["verify_failures"])


def test_a_far_bid_without_its_own_finding_fails():
    result = verify_sources_node(state(findings=clean_findings()[:1]))

    assert result["verify_ok"] is False
    assert any("Bora" in failure and "finding" in failure for failure in result["verify_failures"])


def test_an_arithmetic_failure_without_its_own_finding_fails():
    bids = state()["bids"]
    bids[0]["arithmetic_ok"] = False
    bids[0]["computed_total"] = 4_900_000.0

    result = verify_sources_node(state(bids=bids))

    assert result["verify_ok"] is False
    assert any("Apex" in failure and "arithmetic" in failure for failure in result["verify_failures"])


def test_a_summary_note_with_a_figure_fails():
    result = verify_sources_node(state(summary_note="The pool has 3 awards."))

    assert result["verify_ok"] is False
    assert any("summary note" in failure and "figure" in failure for failure in result["verify_failures"])


def test_a_summary_note_with_a_number_word_fails():
    result = verify_sources_node(state(summary_note="Three awards cover similar work."))

    assert result["verify_ok"] is False
    assert any("summary note" in failure and "number word" in failure
               for failure in result["verify_failures"])


def test_a_finding_note_with_a_bidder_name_fails():
    notes = {"pool": POOL_NOTE, "bid:2": "Bora should be asked about the scope."}

    result = verify_sources_node(state(finding_notes=notes))

    assert result["verify_ok"] is False
    assert any("bid:2" in failure and "bidder" in failure for failure in result["verify_failures"])


def test_notes_over_the_word_limit_fail():
    result = verify_sources_node(state(summary_note=" ".join(["word"] * 41)))

    assert result["verify_ok"] is False
    assert any("40 words" in failure for failure in result["verify_failures"])


def test_a_degraded_report_verifies_without_notes():
    result = verify_sources_node(state(summary_note=None, finding_notes={},
                                       findings=[{**finding, "note": None}
                                                 for finding in clean_findings()],
                                       report_degraded=True))

    assert result["verify_ok"] is True, result["verify_failures"]


def test_the_node_never_calls_a_tool_or_a_model(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("verify_sources must not call a tool or the model")

    import agent.nodes.verify_sources as node

    for name in dir(node):
        if name.startswith(("flag_data", "benchmark_price", "draft_review_file", "ask_json")):
            monkeypatch.setattr(node, name, explode)

    assert verify_sources_node(state())["verify_ok"] is True


def test_a_thin_pool_must_say_so_in_the_report():
    benchmark = {"n": 3, "confidence": "insufficient", "median_kes": None, "q1_kes": None,
                 "q3_kes": None, "sources": ["a01"],
                 "bids": [{"bidder": "Apex", "total": 5_000_000.0, "pct_vs_median": None,
                           "position": None}]}
    findings = [{"kind": "pool", "text": "Only 3 comparable awards were found.",
                 "sources": [{"kind": "pool", "award_id": "a01"}], "note": POOL_NOTE}]

    result = verify_sources_node(state(
        benchmark=benchmark, summary_note=POOL_NOTE, finding_notes={"pool": POOL_NOTE},
        findings=findings, sources=[state()["sources"][0]], pool=[award("a01")],
        summary="The pool is too small."))

    assert result["verify_ok"] is False
    assert any(NOT_ENOUGH in failure for failure in result["verify_failures"])


def test_a_thin_pool_that_says_so_verifies():
    benchmark = {"n": 3, "confidence": "insufficient", "median_kes": None, "q1_kes": None,
                 "q3_kes": None, "sources": ["a01"],
                 "bids": [{"bidder": "Apex", "total": 5_000_000.0, "pct_vs_median": None,
                           "position": None}]}
    findings = [{"kind": "pool", "text": "Only 3 comparable awards were found.",
                 "sources": [{"kind": "pool", "award_id": "a01"}], "note": POOL_NOTE}]

    result = verify_sources_node(state(
        benchmark=benchmark, summary_note=POOL_NOTE, finding_notes={"pool": POOL_NOTE},
        findings=findings, sources=[state()["sources"][0]], pool=[award("a01")],
        summary="The pool is too small.",
        review_markdown="# report\n\n" + NOT_ENOUGH + "\n", bids=[]))

    assert result["verify_ok"] is True, result["verify_failures"]


def test_a_thin_pool_may_not_label_a_bid_far_above_or_far_below():
    state = {"run_id": "run-1", "review_markdown": "# Review\n\n" + NOT_ENOUGH + "\n",
             "findings": [], "sources": [], "summary": "", "summary_note": None,
             "finding_notes": {}, "report_degraded": True,
             "bids": [{"bidder": "Bora Contractors (K) Ltd", "stated_total": 8650000.0}],
             "pool": [], "pool_size": 2,
             "benchmark": {"n": 2, "confidence": "insufficient", "median_kes": None,
                           "q1_kes": None, "q3_kes": None,
                           "bids": [{"bidder": "Bora Contractors (K) Ltd", "total": 8650000.0,
                                     "pct_vs_median": 228639.5, "position": "far_above"}]}}

    result = verify_sources_node(state)

    assert result["verify_ok"] is False
    assert any("no position" in failure or "cannot be labelled" in failure
               for failure in result["verify_failures"])


def test_a_thin_pool_may_not_carry_a_percentage_at_all():
    state = {"run_id": "run-1",
             "review_markdown": "# Review\n\nNot enough comparable awards to benchmark these bids.\n",
             "findings": [], "sources": [], "summary": "", "summary_note": None,
             "finding_notes": {}, "report_degraded": True, "bids": [], "pool": [],
             "pool_size": 2,
             "benchmark": {"n": 2, "confidence": "insufficient", "median_kes": None,
                           "q1_kes": None, "q3_kes": None,
                           "bids": [{"bidder": "Bora", "total": 8650000.0,
                                     "pct_vs_median": 228639.5, "position": "far_above"}]}}

    result = verify_sources_node(state)

    assert result["verify_ok"] is False


def test_a_real_pool_may_still_say_far_above():
    findings = [{"kind": "pool", "text": "Awards set the context.",
                 "sources": [{"kind": "pool", "award_id": "a01"}], "note": POOL_NOTE},
                {"kind": "bid", "text": "Bora is far above the upper quartile.",
                 "sources": [{"kind": "bid", "bidder": "Bora", "file": "bora.pdf", "page": 1},
                             {"kind": "pool", "award_id": "a01"}], "note": BID_NOTE}]
    state = {"run_id": "run-1",
             "review_markdown": "# Review\n\nBora is far above the upper quartile.\n",
             "findings": findings, "summary": POOL_NOTE, "summary_note": POOL_NOTE,
             "finding_notes": {"pool": POOL_NOTE, "bid:1": BID_NOTE}, "report_degraded": False,
             "sources": [{"award_id": "a01", "value_kes": 100.0}],
             "bids": [{"bidder": "Bora", "file": "bora.pdf", "total_page": 1,
                       "stated_total": 8650000.0, "arithmetic_ok": True, "status": "ok"}],
             "pool": [{"award_id": "a01", "value_kes": 100.0}], "pool_size": 17,
             "benchmark": {"n": 17, "confidence": "high", "median_kes": 2860000.0,
                           "q1_kes": 1.0, "q3_kes": 3.0,
                           "bids": [{"bidder": "Bora", "total": 8650000.0,
                                     "pct_vs_median": 204.6, "position": "far_above"}]}}

    result = verify_sources_node(state)

    assert not [failure for failure in result["verify_failures"]
                if "no position" in failure or "cannot be labelled" in failure]
    assert result["verify_ok"] is True, result["verify_failures"]


def test_a_whole_run_from_candidates_to_a_verified_report(monkeypatch, audit_conn):
    from agent.nodes import draft, quality_check, score
    from agent.nodes.draft import draft_node
    from agent.nodes.quality_check import quality_check_node
    from agent.nodes.score import score_node
    from agent.tools import benchmark_price, draft_review_file, flag_data_quality

    monkeypatch.setattr(quality_check, "flag_data_quality", flag_data_quality)
    monkeypatch.setattr(quality_check, "ask_json",
                        lambda name, payload: {"judgements": {a["award_id"]: {"verdict": "same_work",
                                                                               "reason": "classroom blocks"}
                                                             for a in payload["awards"]}}
                        if name == "quality_similarity_judgement" else {"verdicts": {}})
    monkeypatch.setattr(score, "benchmark_price", benchmark_price)

    def fake_wording(prompt_name, payload):
        assert prompt_name == "draft_review_wording"
        keys = [finding["key"] for finding in payload["findings"]]
        return {"summary_note": "The awards cover similar classroom work.",
                "finding_notes": {key: "The scope should be read with the total." for key in keys}}

    monkeypatch.setattr(draft, "ask_json", fake_wording)
    monkeypatch.setattr(draft, "draft_review_file", draft_review_file)

    pool_rows = [dict(award(f"a{i:02d}", float(i) * 500_000.0 + 500_000.0),
                      title="Classroom block construction") for i in range(1, 13)]
    current = {"run_id": "run-e2e", "tender_ref": "TENDER/NC/2026/014",
               "description": "construction of classroom blocks", "candidates": pool_rows,
               "quality_attempts": 0,
               "bids": [{"bidder": "Apex", "file": "apex.pdf", "total_page": 1,
                         "tender_ref": "TENDER/NC/2026/014", "currency": "KES",
                         "items": [], "stated_total": 6_000_000.0, "computed_total": 6_000_000.0,
                         "status": "ok", "arithmetic_ok": True, "issues": []},
                        {"bidder": "Bora", "file": "bora.pdf", "total_page": 2,
                         "tender_ref": "TENDER/NC/2026/014", "currency": "KES",
                         "items": [], "stated_total": 12_000_000.0, "computed_total": 12_000_000.0,
                         "status": "ok", "arithmetic_ok": True, "issues": []}],
               "search": {"match": "loose", "category": "works", "min_year": None, "attempts": 1},
               "verify_rounds": 0}

    current.update(quality_check_node(current))
    current.update(score_node(current))
    current.update(draft_node(current))
    result = verify_sources_node(current)

    assert current["pool_size"] == 12
    assert current["benchmark"]["confidence"] == "medium"
    assert "## Findings" in current["review_markdown"]
    assert result["verify_ok"] is True, result["verify_failures"]


def test_a_note_with_a_figure_never_reaches_a_verified_report(monkeypatch):
    from agent.nodes import draft
    from agent.nodes.draft import draft_node
    from agent.tools import draft_review_file

    monkeypatch.setattr(draft, "draft_review_file", draft_review_file)
    monkeypatch.setattr(draft, "ask_json", lambda name, payload: {
        "summary_note": "The pool has 999.5 awards.", "finding_notes": {}})

    current = state()
    current.update(draft_node(current))
    result = verify_sources_node(current)

    assert current["review_markdown"] == ""
    assert result["verify_ok"] is False
    assert any("no review" in failure for failure in result["verify_failures"])
