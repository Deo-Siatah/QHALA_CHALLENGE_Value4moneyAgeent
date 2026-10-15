import pytest
from copy import deepcopy

from mcp_server.tools.draft_review_file import render_review, draft_review_file, ReviewError

NOTICE = ("Evidence for committee review. This file does not recommend an award. "
          "Bids are synthetic demonstration data. Past awards are public Kenya OCDS records.")
NOT_ENOUGH = "Not enough comparable awards to benchmark these bids."

FORBIDDEN = ["recommend", "winner", "should win", "overpriced", "gouging", "rigging", "rigged",
             "fraud", "corrupt"]


def base_review():
    return {
        "run_id": "run-2026-001",
        "tender_ref": "TENDER/NC/2026/014",
        "summary": "Two bids fall inside the normal range for this kind of work, one sits above it.",
        "benchmark": {
            "n": 6,
            "confidence": "high",
            "median_kes": 3_000_000.0,
            "q1_kes": 2_000_000.0,
            "q3_kes": 4_000_000.0,
            "sources": ["a01", "a02", "a03", "a04", "a05", "a06"],
            "bids": [
                {"bidder": "Apex", "total": 3_000_000.0, "pct_vs_median": 0.0, "position": "within_range"},
                {"bidder": "Bora", "total": 5_000_000.0, "pct_vs_median": 66.7, "position": "far_above"},
            ],
        },
        "search": {"match": "strict", "category": "works", "min_year": 2023, "attempts": 2},
        "excluded": {"no_value": 2, "not_comparable": 1},
        "bids": [
            {"bidder": "Apex", "arithmetic_issues": [], "comment": "Sits on the median of six awards."},
            {"bidder": "Bora", "arithmetic_issues": ["unit price line missing"], "comment": "Far above the pool."},
        ],
        "findings": [
            {"text": "Six awards of similar classroom work fall between 2,000,000 and 4,000,000 KES.",
             "sources": ["a01", "a02"]},
            {"text": "One bid total is 66.7% above the median of that pool.", "sources": ["a03", "a04"]},
        ],
        "sources": [
            {"award_id": "a01", "ocid": "ocid-001", "data_year": 2024, "buyer_name": "Ministry of Education",
             "title": "Classroom construction", "value_kes": 2_000_000.0},
            {"award_id": "a02", "ocid": "ocid-002", "data_year": 2024, "buyer_name": "County Government",
             "title": "Classroom renovation", "value_kes": 3_000_000.0},
            {"award_id": "a03", "ocid": "ocid-003", "data_year": 2023, "buyer_name": "Ministry of Education",
             "title": "Classroom works", "value_kes": 4_000_000.0},
            {"award_id": "a04", "ocid": "ocid-004", "data_year": 2025, "buyer_name": "City Council",
             "title": "School block construction", "value_kes": 5_000_000.0},
        ],
    }


def insufficient_review():
    review = base_review()
    review["benchmark"] = {
        "n": 3,
        "confidence": "insufficient",
        "median_kes": None,
        "q1_kes": None,
        "q3_kes": None,
        "sources": ["a01", "a02", "a03"],
        "bids": [
            {"bidder": "Apex", "total": 3_000_000.0, "pct_vs_median": None, "position": None},
            {"bidder": "Bora", "total": 5_000_000.0, "pct_vs_median": None, "position": None},
        ],
    }
    return review


def test_all_sections_appear_in_order():
    md = render_review(base_review())["markdown"]
    headings = ["# ", "## Summary", "## Comparison pool", "## Bids", "## Findings",
                "## Limitations", "## Sources"]

    positions = [md.index(h) for h in headings]
    assert positions == sorted(positions)
    assert "TENDER/NC/2026/014" in md
    assert "run-2026-001" in md
    assert NOTICE in md
    assert "are contract-level totals" in md
    assert "not proof of anything" in md
    assert "adjustable settings" in md


def test_pool_section_shows_statistics_search_and_exclusions():
    review = base_review()
    md = render_review(review)["markdown"]
    pool_section = md[md.index("## Comparison pool"):md.index("## Bids")]

    assert "6" in pool_section
    assert "3,000,000.00" in pool_section
    assert "2,000,000.00" in pool_section and "4,000,000.00" in pool_section
    assert "high" in pool_section
    assert "match=strict" in pool_section
    assert "category=works" in pool_section
    assert "min_year=2023" in pool_section
    assert "attempts=2" in pool_section
    assert "no_value" in pool_section and "not_comparable" in pool_section


def test_bid_table_rows():
    md = render_review(base_review())["markdown"]
    bids_section = md[md.index("## Bids"):md.index("## Findings")]

    assert "Apex" in bids_section and "Bora" in bids_section
    assert "3,000,000.00" in bids_section and "5,000,000.00" in bids_section
    assert "0.0%" in bids_section and "66.7%" in bids_section
    assert "within_range" in bids_section and "far_above" in bids_section
    assert "unit price line missing" in bids_section
    assert "Sits on the median of six awards." in bids_section


def test_findings_cite_sources_and_sources_table_lists_them():
    review = base_review()
    md = render_review(review)["markdown"]

    assert "1. Six awards of similar classroom work" in md
    assert "Sources: a01, a02" in md
    assert "Sources: a03, a04" in md
    sources_table = md[md.index("## Sources"):]
    for award_id in ["a01", "a02", "a03", "a04"]:
        assert award_id in sources_table
    assert "ocid-001" in sources_table and "ocid-004" in sources_table
    assert "Ministry of Education" in sources_table
    assert "Classroom construction" in sources_table
    assert "2023" in sources_table and "2025" in sources_table
    assert "2,000,000.00" in sources_table
    assert "2023-2025" in sources_table


def test_finding_without_sources_raises():
    review = base_review()
    review["findings"][0]["sources"] = []

    with pytest.raises(ReviewError) as err:
        render_review(review)

    assert "finding 1" in str(err.value)


def test_finding_with_unknown_award_id_raises():
    review = base_review()
    review["findings"][1]["sources"] = ["a99"]

    with pytest.raises(ReviewError) as err:
        render_review(review)

    assert "a99" in str(err.value)


@pytest.mark.parametrize("word", FORBIDDEN)
def test_forbidden_word_in_summary_raises(word):
    review = base_review()
    review["summary"] = f"This pool says {word} things about the bids."

    with pytest.raises(ReviewError) as err:
        render_review(review)

    assert word in str(err.value)


@pytest.mark.parametrize("word", FORBIDDEN)
def test_forbidden_word_in_comment_raises(word):
    review = base_review()
    review["bids"][0]["comment"] = f"The bidder looks {word} on this work."

    with pytest.raises(ReviewError) as err:
        render_review(review)

    assert word in str(err.value)


@pytest.mark.parametrize("word", FORBIDDEN)
def test_forbidden_word_in_finding_raises(word):
    review = base_review()
    review["findings"][0]["text"] = f"The buyer should look at {word} behaviour."

    with pytest.raises(ReviewError) as err:
        render_review(review)

    assert word in str(err.value)


def test_fixed_notice_text_does_not_trigger_the_scan():
    md = render_review(base_review())["markdown"]

    assert "does not recommend an award" in md


def test_insufficient_shows_not_enough_evidence_and_no_statistics():
    md = render_review(insufficient_review())["markdown"]
    pool_section = md[md.index("## Comparison pool"):md.index("## Bids")]

    assert NOT_ENOUGH in pool_section
    assert "Median" not in pool_section
    assert "Normal range" not in pool_section
    bids_section = md[md.index("## Bids"):md.index("## Findings")]
    assert "within_range" not in bids_section
    assert "far_above" not in bids_section
    assert bids_section.count("n/a") >= 4


def test_same_input_same_output_and_input_not_mutated():
    review = base_review()
    before = deepcopy(review)

    first = render_review(review)
    second = render_review(review)

    assert first == second
    assert review == before
    assert draft_review_file(review) == first
