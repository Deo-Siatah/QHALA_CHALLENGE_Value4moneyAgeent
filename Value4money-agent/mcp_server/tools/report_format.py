# The one place report figures and labels are written. Money, percentages, positions and source
# references all leave through these functions, so the Markdown, LaTeX, PDF and browser cannot drift.

from typing import Any, Dict, Union

EXCLUSION_LABELS = {
    "different_work": "different work",
    "different_scale": "different scale",
    "scale_mismatch": "different scale",
    "no_value": "no value",
    "value_not_positive": "no value",
    "non_kes": "not KES",
    "duplicate_row": "duplicate row",
    "missing_award_id": "missing award id",
    "suspect_excluded": "suspect record",
    "multi_scope": "multiple scopes",
    "value_unusable": "unusable value",
    "duplicate": "duplicate row",
    "suspected_typo": "suspected typo",
}

POSITION_LABELS = {
    "within_range": "within the normal range",
    "above_range": "above the normal range",
    "below_range": "below the normal range",
    "far_above": "far above the upper quartile",
    "far_below": "far below the lower quartile",
}


def amount(value: Union[int, float]) -> str:
    """Write a KES amount with thousands separators and two decimals, without the currency."""
    return f"{float(value):,.2f}"


def kes(value: Union[int, float]) -> str:
    """Write a KES amount with the currency in front."""
    return f"KES {amount(value)}"


def kes_short(value: Union[int, float]) -> str:
    """Write a KES amount in a short form for prose."""
    number = float(value)
    if abs(number) >= 1_000_000:
        return f"KES {number / 1_000_000:,.2f} million"
    if abs(number) >= 1_000:
        return f"KES {number / 1_000:,.2f} thousand"
    return kes(number)


def pct_phrase(pct: Union[int, float, None]) -> str:
    """Write a percentage against the median in whole numbers and one direction only."""
    if pct is None:
        return "n/a"
    number = float(pct)
    if number == 0:
        return "on the median"
    direction = "above" if number > 0 else "below"
    if abs(number) < 1:
        return f"less than 1% {direction}"
    return f"{round(abs(number))}% {direction}"


def position_label(position: str) -> str:
    """Write a benchmark position as plain words."""
    return POSITION_LABELS.get(position, position.replace("_", " "))


def source_label(source: Any) -> str:
    """Write one finding source as the reference a committee can look up."""
    if isinstance(source, str):
        return source
    if hasattr(source, "model_dump"):
        source = source.model_dump()
    if not isinstance(source, Dict):
        return str(source)
    if source.get("kind") == "bid":
        label = str(source.get("bidder") or source.get("file") or "bid document")
        if source.get("file"):
            label = f"{label}, {source['file']}"
        if source.get("page") is not None:
            label = f"{label} p.{source['page']}"
        return label
    return str(source.get("award_id") or source.get("ocid") or "source")


def exclusion_label(code: str) -> str:
    """Write an exclusion code as plain words."""
    return EXCLUSION_LABELS.get(code, code.replace("_", " "))
