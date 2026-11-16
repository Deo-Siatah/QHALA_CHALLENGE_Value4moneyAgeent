from mcp_server.tools.report_format import (
    amount,
    exclusion_label,
    kes,
    kes_short,
    pct_phrase,
    position_label,
    source_label,
)


def test_money_is_written_once_with_kes_and_two_decimals():
    assert kes(2_373_169.69) == "KES 2,373,169.69"
    assert amount(2_373_169.69) == "2,373,169.69"
    assert kes_short(2_373_169.69) == "KES 2.37 million"


def test_percentages_are_whole_numbers_and_never_double_negative():
    assert pct_phrase(118.6) == "119% above"
    assert pct_phrase(-48.3) == "48% below"
    assert pct_phrase(0) == "on the median"
    assert pct_phrase(0.4) == "less than 1% above"
    assert pct_phrase(-0.4) == "less than 1% below"


def test_positions_and_sources_have_one_plain_wording():
    assert position_label("far_above") == "far above the upper quartile"
    assert position_label("below_range") == "below the normal range"
    assert position_label("within_range") == "within the normal range"
    assert source_label({"kind": "pool", "award_id": "a01"}) == "a01"
    assert source_label({"kind": "bid", "bidder": "Apex", "file": "apex.pdf",
                         "page": 2}) == "Apex, apex.pdf p.2"


def test_exclusion_codes_become_plain_labels():
    assert exclusion_label("different_work") == "different work"
    assert exclusion_label("scale_mismatch") == "different scale"
    assert exclusion_label("no_value") == "no value"
