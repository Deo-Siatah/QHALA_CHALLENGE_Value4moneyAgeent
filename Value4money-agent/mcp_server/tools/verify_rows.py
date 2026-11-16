"""Check proposed bid rows against the page they came from.

Language model output is never trusted on its own. A row survives only when
every number in it can be found in the source page text and its quantity times
its unit price reconciles with its line total. Anything else is rejected and
reported, so a hostile PDF cannot smuggle invented figures into the file.
"""
import re
from typing import Any

_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def _amount(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.lower().replace(",", "").replace("/=", "")
        cleaned = re.sub(r"\b(?:kes|ksh|kshs|shs|sh)\b", "", cleaned).strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _page_numbers(text: str) -> set[float]:
    numbers = set()
    for token in _NUMBER.findall(text):
        try:
            numbers.add(float(token.replace(",", "")))
        except ValueError:
            continue
    return numbers


def verify_extracted_rows(page_text: str, rows: Any) -> dict:
    """Return accepted rows and rejected rows with the reason each failed."""
    if not isinstance(rows, list):
        rows = [rows]

    seen = _page_numbers(page_text)
    accepted: list[dict] = []
    rejected: list[dict] = []

    for index, row in enumerate(rows, 1):
        reason = _check(row, page_text, seen)
        if reason:
            rejected.append({"row": row, "reason": reason})
            continue
        clean = dict(row)
        clean.setdefault("item_label", str(index))
        accepted.append(clean)

    return {"accepted": accepted, "rejected": rejected}


def _check(row: Any, page_text: str, seen: set[float]) -> str | None:
    if not isinstance(row, dict):
        return "Row is not an object"
    description = row.get("description")
    if not isinstance(description, str) or not description.strip():
        return "Row has no description"

    numbers = {}
    for field in ("quantity", "unit_price", "line_total"):
        value = _amount(row.get(field))
        if value is None:
            return f"Row has no valid {field}"
        numbers[field] = value

    source_text = row.get("source_text")
    if source_text is not None and str(source_text) not in page_text:
        return "Row source text is not on the page"

    for field, value in numbers.items():
        if value not in seen:
            return f"{field} {value:g} is not on the page"

    expected = numbers["quantity"] * numbers["unit_price"]
    if abs(expected - numbers["line_total"]) > 0.01:
        return (f"{numbers['quantity']:g} x {numbers['unit_price']:g} = "
                f"{expected:.2f} does not reconcile with line total "
                f"{numbers['line_total']:.2f}")

    return None
