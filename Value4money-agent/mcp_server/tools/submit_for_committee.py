# File the approved report. The only tool that writes outputs, so it refuses without a named human.
# It checks the approver, the run_id and the body first, then inserts the row and writes the file.
# Row and file land together: if the file write fails, the row is rolled back and nothing is filed.

import re
from pathlib import Path
from typing import Any, Dict, Optional
from config import settings
from ..db import get_conn
from psycopg.types.json import Jsonb
from .report_fingerprint import fingerprint_markdown
from .report_html import render_html
from .report_model import ReportModel

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


def submit_report(conn, outputs_dir: Path, run_id: str, report_md: str, approved_by: str,
                  review_json: Optional[Dict[str, Any]] = None) -> dict:
    """Insert the report row and write its Markdown and print HTML, or do neither."""
    name = _check_approved_by(approved_by)
    if not isinstance(report_md, str) or not report_md.strip():
        raise SubmitError("report_md is empty: there is nothing to file")
    if not isinstance(run_id, str) or not RUN_ID_PATTERN.match(run_id):
        raise SubmitError(f"run_id must match {RUN_ID_PATTERN.pattern}, got {run_id!r}")
    if conn.execute("SELECT id FROM reports WHERE run_id = %s", (run_id,)).fetchone():
        raise SubmitError(f"run_id '{run_id}' has already been filed")

    fingerprint = fingerprint_markdown(report_md)
    saved = conn.execute(
        "INSERT INTO reports (run_id, body_md, approved_by, fingerprint, review_json) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id, created_at",
        (run_id, report_md, name, fingerprint,
         Jsonb(review_json) if review_json is not None else None)).fetchone()

    html = None
    if review_json is not None:
        try:
            html = render_html(ReportModel(**review_json), fingerprint=fingerprint,
                               approved_by=name, created_at=saved["created_at"])
        except Exception as exc:
            conn.rollback()
            raise SubmitError(f"review_json could not be rendered: {exc}") from exc

    folder = Path(outputs_dir) / "reports"
    file_path = folder / f"{run_id}.md"
    html_path = folder / f"{run_id}.html"
    written = [file_path] + ([html_path] if html is not None else [])
    try:
        folder.mkdir(parents=True, exist_ok=True)
        file_path.write_text(report_md, encoding="utf-8")
        if html is not None:
            html_path.write_text(html, encoding="utf-8")
    except OSError as exc:
        conn.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        raise SubmitError(f"could not write the report files: {exc}") from exc
    conn.commit()
    return {"report_id": saved["id"], "run_id": run_id, "approved_by": name,
            "file_path": str(file_path),
            "html_file_path": str(html_path) if html is not None else None,
            "submitted_at": saved["created_at"], "fingerprint": fingerprint}


def submit_for_committee(run_id: str, report_md: str, approved_by: str,
                         review_json: Optional[Dict[str, Any]] = None) -> dict:
    """File the approved report to the database and settings.outputs_dir."""
    conn = get_conn()
    try:
        return submit_report(conn, settings.outputs_dir, run_id, report_md, approved_by,
                             review_json=review_json)
    finally:
        conn.close()
