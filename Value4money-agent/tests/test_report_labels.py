import pytest

from mcp_server.tools.report_labels import (
    bottom_line,
    evidence_label,
    prepared_date,
    reason_label,
    state_label,
    state_shape,
)


def test_every_position_has_one_plain_word_and_one_silhouette():
    assert state_label("within_range") == "within the usual price"
    assert state_label("above_range") == "above the usual price"
    assert state_label("below_range") == "below the usual price"
    assert state_label("far_above") == "far above the usual price"
    assert state_label("far_below") == "far below the usual price"
    assert state_label(None) == "not compared"

    assert state_shape("within_range") == "hollow-circle"
    assert state_shape("above_range") == "triangle-up"
    assert state_shape("below_range") == "triangle-down"
    assert state_shape("far_above") == "filled-circle"
    assert state_shape("far_below") == "diamond"
    assert state_shape(None) == "square"


def test_the_primary_silhouettes_are_not_reused():
    shapes = [state_shape(position) for position in
              ("within_range", "above_range", "below_range", "far_above", "far_below")]

    assert len(set(shapes)) == len(shapes)


def test_evidence_strength_is_three_plain_words():
    assert evidence_label("high") == "Strong"
    assert evidence_label("medium") == "Fair"
    assert evidence_label("insufficient") == "Not enough evidence"


@pytest.mark.parametrize("code,word", [
    ("different_work", "different work"),
    ("scale_mismatch", "different scale"),
    ("multi_scope", "more than one kind of work"),
    ("value_unusable", "value cannot be used"),
    ("duplicate", "duplicate record"),
    ("duplicate_row", "duplicate record"),
    ("suspected_typo", "possible typing error"),
    ("value_not_positive", "no usable value"),
    ("non_kes", "not in KES"),
    ("missing_award_id", "no award id"),
])
def test_reason_codes_become_plain_words(code, word):
    assert reason_label(code) == word


def test_bottom_line_mixed_says_how_many_are_worth_a_question():
    assert bottom_line(within=2, questions=1, n=3, unreadable=0) == (
        "2 of 3 bids are within the usual price for this work. "
        "1 is worth a question first.")


def test_bottom_line_all_within_is_one_sentence():
    assert bottom_line(within=3, questions=0, n=3, unreadable=0) == (
        "All 3 bids are within the usual price for this work.")


def test_bottom_line_insufficient_says_not_enough_comparable_awards():
    text = bottom_line(within=0, questions=0, n=2, unreadable=0, insufficient=True)

    assert text.startswith("Not enough comparable awards")
    assert "not compared" in text


def test_bottom_line_appends_bids_that_could_not_be_read():
    assert bottom_line(within=2, questions=1, n=4, unreadable=1) == (
        "2 of 4 bids are within the usual price for this work. "
        "1 is worth a question first. 1 bid could not be read and is not compared.")


def test_bottom_line_with_nothing_readable_says_so():
    assert bottom_line(within=0, questions=0, n=0, unreadable=0) == (
        "No bid could be read, so there is nothing to compare.")


def test_prepared_date_is_east_africa_time_on_the_same_moment():
    assert prepared_date("2026-10-19T11:09:22+00:00") == "19 October 2026, 14:09 EAT"


def test_a_missing_start_time_is_said_rather_than_invented():
    assert prepared_date("") == "Not recorded"
