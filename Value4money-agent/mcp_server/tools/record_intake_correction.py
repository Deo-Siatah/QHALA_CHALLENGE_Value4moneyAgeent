"""Record a named person's correction to the intake, with the reason they gave.

Intake is where a misread document becomes a wrong search and then a wrong benchmark, so a human
who changes a value has to be on the record next to it. A role such as "agent" is refused: the
point of the gate is that a person can be asked about the change afterwards.
"""
from typing import Any

PLACEHOLDERS = {"agent", "ai", "system", "bot", "auto", "none", "n/a", "unknown"}


def record_intake_correction(field: str, value: Any, approved_by: str, reason: str = "") -> dict:
    """Return the correction as an audited record, refusing a blank field or an unnamed person."""
    if not isinstance(field, str) or not field.strip():
        raise ValueError(f"field must be a non-empty string, got {field!r}")
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"value for {field!r} is empty")
    if value is None:
        raise ValueError(f"value for {field!r} is empty")
    name = (approved_by or "").strip()
    if len(name) < 2 or name.lower() in PLACEHOLDERS:
        raise ValueError(f"approved_by must be the name of a person, got {approved_by!r}")
    return {"field": field.strip(), "value": value, "approved_by": name,
            "reason": (reason or "").strip(), "recorded": True}
