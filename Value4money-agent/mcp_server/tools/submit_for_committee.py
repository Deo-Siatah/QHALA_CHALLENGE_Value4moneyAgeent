# File the approved report. The only tool that writes outputs, so it refuses without a named human.
# It checks the approver, the run_id and the body first, then inserts the row and writes the file.
# Row and file land together: if the file write fails, the row is rolled back and nothing is filed.

import re
from pathlib import Path
from typing import Optional
from config import settings
from ..db import get_conn

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
PLACEHOLDERS = {"agent", "ai", "system", "bot", "auto", "none", "n/a", "unknown"}


class SubmitError(ValueError):
    """Raised when a submit is not allowed; nothing is written."""


def _check_approved_by(approved_by: Optional[str]) -> str:
    """Refuse blank, too-short and placeholder approvers, and return the trimmed name."""
    name = approved_by.strip() if isinstance(approved_by, str) else ""
    if len(name) < 2:
        raise SubmitError(f"approved_by must be a named human, got {approved_by!r}")
    if name.lower() in PLACEHOLDERS:
        raise SubmitError(f"approved_by must be a named human, got placeholder {name!r}")
    return name


def submit_report(conn, outputs_dir: Path, run_id: str, report_md: str, approved_by: str) -> dict:
    """Insert the report row and write the markdown file, or do neither."""
    name = _check_approved_by(approved_by)
    if not isinstance(report_md, str) or not report_md.strip():
        raise SubmitError("report_md is empty: there is nothing to file")
    if not isinstance(run_id, str) or not RUN_ID_PATTERN.match(run_id):
        raise SubmitError(f"run_id must match {RUN_ID_PATTERN.pattern}, got {run_id!r}")
    if conn.execute("SELECT id FROM reports WHERE run_id = %s", (run_id,)).fetchone():
        raise SubmitError(f"run_id '{run_id}' has already been filed")

    saved = conn.execute(
        "INSERT INTO reports (run_id, body_md, approved_by) VALUES (%s, %s, %s) RETURNING id, created_at",
        (run_id, report_md, name)).fetchone()

    file_path = Path(outputs_dir) / "reports" / f"{run_id}.md"
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(report_md, encoding="utf-8")
    except OSError as exc:
        conn.rollback()
        raise SubmitError(f"could not write {file_path}: {exc}") from exc
    conn.commit()
    return {"report_id": saved["id"], "run_id": run_id, "approved_by": name,
            "file_path": str(file_path), "submitted_at": saved["created_at"]}


def submit_for_committee(run_id: str, report_md: str, approved_by: str) -> dict:
    """File the approved report to the database and settings.outputs_dir."""
    conn = get_conn()
    try:
        return submit_report(conn, settings.outputs_dir, run_id, report_md, approved_by)
    finally:
        conn.close()
