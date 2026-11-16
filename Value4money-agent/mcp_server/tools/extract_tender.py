"""Read the tender document's labelled fields with their page and line.

Fields are taken only from lines that carry an explicit label. A value typed
into the form is accepted only when that same text can be found in the PDF;
otherwise it is rejected so the committee sees a source, never an assumption.
"""
import re
from pathlib import Path

import pypdf
from pypdf.errors import PyPdfError

from ..paths import resolve_inside

_FIELDS = {
    "reference": r"tender\s*(?:no\.?|number|ref(?:erence)?)",
    "title": r"title|tender\s+title|description",
    "buyer": r"procuring\s+entity|employer|buyer",
    "county": r"county|location",
    "method": r"procurement\s+method|method",
    "closing_date": r"closing\s+date|deadline|submission\s+deadline",
    "budget_kes": r"budget|estimated\s+(?:cost|value)|estimate",
}
_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def _read_pages(path: Path) -> list[dict]:
    try:
        with open(path, "rb") as handle:
            reader = pypdf.PdfReader(handle)
            return [{"page": number, "text": page.extract_text() or ""}
                    for number, page in enumerate(reader.pages, 1)]
    except PyPdfError as exc:
        raise ValueError(f"Unable to extract text from PDF: {exc}")


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" \t:-")


def _amount(value: str) -> float | None:
    matches = _NUMBER.findall(value)
    if not matches:
        return None
    try:
        return float(matches[-1].replace(",", ""))
    except ValueError:
        return None


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _find(pages: list[dict], value: str) -> dict | None:
    needle = _normalise(value)
    for page in pages:
        for line in page["text"].splitlines():
            if needle and needle in _normalise(line):
                return {"page": page["page"], "text": line.strip()}
    return None


def extract_tender_pdf(path: str | Path, tender_dir: str | Path,
                       filled: dict | None = None) -> dict:
    """Extract labelled tender fields, verifying any supplied values."""
    resolved = resolve_inside(path, tender_dir, "tenders")
    if not resolved.exists():
        raise ValueError("File not found")

    pages = _read_pages(resolved)
    fields: dict[str, dict] = {}
    rejected: list[dict] = []

    for page in pages:
        for line in page["text"].splitlines():
            text = line.strip()
            if not text:
                continue
            for name, pattern in _FIELDS.items():
                if name in fields:
                    continue
                match = re.match(rf"^(?:{pattern})\s*[:\-]\s*(.+)$", text, re.I)
                if not match:
                    continue
                raw = match.group(1).strip()
                value = _amount(raw) if name == "budget_kes" else _clean(raw)
                if value not in (None, ""):
                    fields[name] = {"value": value,
                                    "source": {"page": page["page"], "text": text}}

    for name, raw in (filled or {}).items():
        value = _amount(str(raw)) if name == "budget_kes" else _clean(str(raw))
        if value in (None, ""):
            rejected.append({"field": name, "value": raw, "reason": "Empty value"})
            continue
        source = _find(pages, str(raw))
        if source is None:
            rejected.append({"field": name, "value": raw,
                             "reason": "Value is not on any page"})
            continue
        if name not in fields:
            fields[name] = {"value": value, "source": source}

    return {
        "fields": fields,
        "missing": [name for name in _FIELDS if name not in fields],
        "rejected": rejected,
        "pages": pages,
    }
