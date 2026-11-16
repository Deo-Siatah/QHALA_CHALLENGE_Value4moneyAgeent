"""Plain words for the report, kept in one place."""

from datetime import datetime, timedelta, timezone
from typing import Optional

EAT = timezone(timedelta(hours=3), "EAT")
NOT_STATED = "Not stated in the documents"

NOTICE = ("Evidence for committee review. This file does not recommend an award. "
          "Bids are synthetic demonstration data. Past awards are public Kenya OCDS records.")

CAUTION_LINES = [
    "Award values are contract-level totals. They carry no scope, quality or location, "
    "so a total alone cannot show whether the work is comparable.",
    "A total far from the usual price is a reason to ask the buyer a question, not proof of anything.",
]

METHOD_POINTS = [
    "Bids are compared with past public awards for similar work.",
    "The usual price is the median award value in that pool.",
    "The normal range is the middle half of the pool, from the lower quartile to the upper quartile.",
    "Far above or far below is a question to ask, not a finding of fault.",
]

GLOSSARY = [
    ("Usual price", "the median value of the comparable awards."),
    ("Normal range", "the middle half of comparable award values, from Q1 to Q3."),
    ("Set aside", "a candidate award not used in the comparison, with the reason shown."),
    ("EAT", "East Africa Time, UTC+03:00."),
]

ASSISTANT_LABEL = "Written by the assistant. Figures in this file are computed by code."
ASSISTANT_MISSING = "No assistant note was available for this report."

QUESTION_STATES = {"above_range", "below_range", "far_above", "far_below"}

STATE_WORDS = {
    "within_range": "within the usual price",
    "above_range": "above the usual price",
    "below_range": "below the usual price",
    "far_above": "far above the usual price",
    "far_below": "far below the usual price",
    None: "not compared",
}

STATE_SHAPES = {
    "within_range": "hollow-circle",
    "above_range": "triangle-up",
    "below_range": "triangle-down",
    "far_above": "filled-circle",
    "far_below": "diamond",
    None: "square",
}

EVIDENCE_WORDS = {
    "high": "Strong",
    "medium": "Fair",
    "insufficient": "Not enough evidence",
}

REASON_WORDS = {
    "different_work": "different work",
    "scale_mismatch": "different scale",
    "multi_scope": "more than one kind of work",
    "value_unusable": "value cannot be used",
    "duplicate": "duplicate record",
    "duplicate_row": "duplicate record",
    "suspected_typo": "possible typing error",
    "value_not_positive": "no usable value",
    "non_kes": "not in KES",
    "missing_award_id": "no award id",
    "invalid_fields": "incomplete record",
    "suspect_excluded": "set aside after review",
    "no_value": "no value",
    "not_comparable": "different work",
    "excluded": "set aside",
}


def state_label(position: Optional[str]) -> str:
    """The plain-word state for one benchmark position."""
    return STATE_WORDS.get(position, "not compared")


def state_shape(position: Optional[str]) -> str:
    """The silhouette that carries the same meaning as the state word."""
    return STATE_SHAPES.get(position, "square")


def evidence_label(confidence: str) -> str:
    """How much evidence the pool holds, in one plain word."""
    return EVIDENCE_WORDS.get(confidence, "Not enough evidence")


def reason_label(code: str) -> str:
    """A reason code as words a committee can read."""
    return REASON_WORDS.get(code, "set aside")


def bottom_line(within: int, questions: int, n: int, unreadable: int,
                insufficient: bool = False) -> str:
    """The one-sentence answer at the top of page one."""
    if n == 0 and not insufficient:
        return "No bid could be read, so there is nothing to compare."
    if insufficient:
        text = ("Not enough comparable awards to set a usual price, so these bids are not compared.")
    elif questions == 0 and within == n and unreadable == 0:
        text = f"All {n} bids are within the usual price for this work."
    else:
        text = (f"{within} of {n} bids are within the usual price for this work. "
                f"{questions} {'is' if questions == 1 else 'are'} worth a question first.")
    if unreadable:
        text += (f" {unreadable} {'bid' if unreadable == 1 else 'bids'} could not be read "
                 f"and {'is' if unreadable == 1 else 'are'} not compared.")
    return text


def prepared_date(value: str) -> str:
    """The run start time in East Africa Time, or a plain refusal to invent one."""
    if not isinstance(value, str) or not value.strip():
        return "Not recorded"
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "Not recorded"
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(EAT).strftime("%d %B %Y, %H:%M EAT")
