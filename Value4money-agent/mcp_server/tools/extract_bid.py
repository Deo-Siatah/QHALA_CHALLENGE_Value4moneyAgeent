"""Read one bid PDF with a strict path first and a tolerant table path second.

The strict parser in ``parse_bid_pdf`` is tried first. When it fails, the pages
are read by position with ``pdfplumber`` so reordered columns, merged headers,
``Ksh`` spellings, ``/=`` suffixes and bill numbers like ``1.1`` still resolve.
Every page is classified as text, scan, blank or garbled and pages that cannot
be read are listed instead of being guessed. Arithmetic is checked, never
corrected. A model may fill remaining pages, but its rows arrive only through
``verify_extracted_rows``.
"""
import re
from pathlib import Path
from typing import Any

import pypdf
from pypdf.errors import PyPdfError

from config import settings
from ..paths import PathOutsideError, resolve_inside
from .parse_bid_pdf import BidParseError, parse_bid
from .verify_rows import verify_extracted_rows

_HEADER_SYNONYMS = {
    "no": {"no", "s no", "s/n", "sn", "item no", "item number"},
    "description": {"description", "item", "particulars", "details",
                    "item description", "goods", "services"},
    "unit": {"unit", "uom", "u o m", "units", "unit of measure"},
    "quantity": {"qty", "quantity", "qnty"},
    "unit_price": {"rate", "unit price", "unit rate", "price", "unit cost"},
    "line_total": {"amount", "total", "line total", "line amount",
                   "value", "cost", "total amount"},
}
_ITEM_LABEL = re.compile(r"^\d+(?:\.\d+)*$")
_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_TOTAL = re.compile(r"^(?:grand\s+)?total\b|^stated\s+total\b")
_SUBTOTAL = re.compile(r"^sub\s*total\b")
_VAT = re.compile(r"^vat\b|^value\s+added\s+tax\b")
_NOISE = re.compile(r"^(?:page|tel|email|signature|date|dear|cover\s+letter)\b")


def _read_pages(path: Path) -> list[dict]:
    try:
        with open(path, "rb") as handle:
            reader = pypdf.PdfReader(handle)
            pages = []
            for number, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ""
                pages.append({"page": number, "text": text,
                              "has_image": bool(getattr(page, "images", []))})
            return pages
    except PyPdfError as exc:
        raise BidParseError(f"Unable to extract text from PDF: {exc}")


def _classify(page: dict) -> str:
    text = page["text"].strip()
    if not text:
        return "scan" if page["has_image"] else "blank"
    if page["has_image"] and len(text) < settings.page_min_chars:
        return "scan"
    ratio = sum(char.isalnum() for char in text) / len(text)
    return "garbled" if ratio < settings.page_garbled_ratio else "text"


def _layout_pages(path: Path, numbers: list[int]) -> dict[int, list[str]]:
    import pdfplumber

    layout: dict[int, list[str]] = {}
    with pdfplumber.open(str(path)) as pdf:
        for number in numbers:
            text = pdf.pages[number - 1].extract_text(layout=True) or ""
            layout[number] = [line for line in text.splitlines() if line.strip()]
    return layout


def _canonical(cell: str) -> str | None:
    cleaned = re.sub(r"[^a-z0-9 ]", " ", cell.lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    for name, words in _HEADER_SYNONYMS.items():
        if cleaned in words:
            return name
    return None


def _split_cells(line: str) -> list[str]:
    if "|" in line:
        return [cell.strip() for cell in line.split("|")]
    cells = [cell.strip() for cell in re.split(r"\s{2,}", line.strip()) if cell.strip()]
    return cells or [line.strip()]


def _header_map(cells: list[str]) -> dict[int, str] | None:
    mapped: dict[int, str] = {}
    for index, cell in enumerate(cells):
        name = _canonical(cell)
        if name and name not in mapped.values():
            mapped[index] = name
    return mapped if len(mapped) >= 3 else None


def _amount(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).lower().replace(",", "").replace("/=", "")
    text = re.sub(r"\b(?:kes|ksh|kshs|shs|sh)\b", "", text).strip()
    if not re.match(r"^-?\d+(?:\.\d+)?$", text):
        return None
    return float(text)


def _last_amount(text: str) -> float | None:
    matches = _NUMBER.findall(text)
    for token in reversed(matches):
        value = _amount(token)
        if value is not None:
            return value
    return None


def _default_columns(count: int) -> list[str] | None:
    if count >= 6:
        return ["no", "description", "unit", "quantity", "unit_price", "line_total"]
    if count == 5:
        return ["no", "description", "quantity", "unit_price", "line_total"]
    if count == 4:
        return ["description", "quantity", "unit_price", "line_total"]
    return None


def _row_item(cells: list[str], header: dict[int, str] | None, page: int,
              line: str, position: int) -> dict | None:
    if header is None:
        columns = _default_columns(len(cells))
        if columns is None:
            return None
        data = dict(zip(columns, cells))
    else:
        data = {name: cells[index] for index, name in header.items() if index < len(cells)}

    description = (data.get("description") or "").strip()
    if len(description) < 2 or not any(char.isalpha() for char in description):
        return None

    quantity = _amount(data.get("quantity"))
    unit_price = _amount(data.get("unit_price"))
    line_total = _amount(data.get("line_total"))
    if quantity is None or unit_price is None:
        return None
    if quantity <= 0 or unit_price <= 0:
        return None
    if line_total is None:
        line_total = quantity * unit_price

    label = (data.get("no") or "").strip()
    if not _ITEM_LABEL.match(label):
        label = str(position)
    match = re.match(r"^(\d+)", label)
    no = int(match.group(1)) if match else position

    return {
        "no": no,
        "item_label": label,
        "description": description,
        "unit": (data.get("unit") or "").strip(),
        "quantity": quantity,
        "unit_price": unit_price,
        "line_total": line_total,
        "page": page,
        "source_text": line,
    }


def _parse_layout_pages(layout: dict[int, list[str]]) -> dict:
    items: list[dict] = []
    subtotal = vat = stated = None
    stated_page = None
    used: set[int] = set()

    for page, lines in layout.items():
        header = None
        for line in lines:
            cells = _split_cells(line)
            found = _header_map(cells)
            if found:
                header = found
                used.add(page)
                continue

            lowered = line.strip().lower()
            if _TOTAL.match(lowered):
                value = _last_amount(line)
                if value is not None:
                    stated = value
                    stated_page = page
                    used.add(page)
                continue
            if _SUBTOTAL.match(lowered):
                value = _last_amount(line)
                if value is not None:
                    subtotal = value
                    used.add(page)
                continue
            if _VAT.match(lowered):
                value = _last_amount(line)
                if value is not None:
                    vat = value
                    used.add(page)
                continue
            if _NOISE.match(lowered):
                continue

            item = _row_item(cells, header, page, line, len(items) + 1)
            if item:
                items.append(item)
                used.add(page)

    return {"items": items, "subtotal": subtotal, "vat": vat,
            "stated_total": stated, "stated_page": stated_page, "used_pages": used}


def _detect_currency(pages: list[dict]) -> str:
    text = "\n".join(page["text"] for page in pages)
    explicit = re.search(r"currency\s*[:\-]\s*([a-z]{3})\b", text, re.I)
    if explicit:
        code = explicit.group(1).upper()
        return "KES" if code == "KSH" else code
    for code in ("USD", "EUR", "GBP", "UGX", "TZS", "ZAR"):
        if re.search(rf"\b{code}\b", text, re.I):
            return code
    if re.search(r"\b(?:kes|ksh|kshs|shs)\b", text, re.I):
        return "KES"
    return ""


def _labelled(lines: list[str], *labels: str) -> str:
    for line in lines:
        lowered = line.lower()
        for label in labels:
            prefix = label.lower() + ":"
            if lowered.startswith(prefix):
                return line[len(label) + 1:].strip()
    return ""


def _page_of(pages: list[dict], needle: str) -> tuple[int | None, str | None]:
    for page in pages:
        for line in page["text"].splitlines():
            if needle and needle.lower() in line.lower():
                return page["page"], line.strip()
    return None, None


def _reconcile(items: list[dict], vat: float | None) -> tuple[float, list[str]]:
    issues = []
    for item in items:
        expected = item["quantity"] * item["unit_price"]
        if abs(expected - item["line_total"]) > 0.01:
            issues.append(
                f"Line {item['item_label']}: {item['quantity']:g} x "
                f"{item['unit_price']:g} = {expected:.2f} but line total is "
                f"{item['line_total']:.2f}"
            )
    return round(sum(item["line_total"] for item in items) + (vat or 0), 2), issues


def _enrich_strict(result: dict, pages: list[dict]) -> list[dict]:
    items = []
    for item in result["items"]:
        page, source = _page_of(pages, item["description"])
        items.append({**item, "item_label": str(item["no"]),
                      "page": page, "source_text": source})
    return items


def extract_bid(path: str | Path, bids_dir: str | Path,
                verified_rows: list[dict] | None = None) -> dict:
    """Extract one bid, falling back to layout tables and then verified rows."""
    resolved = resolve_inside(path, bids_dir, "bids")

    if not resolved.exists():
        raise BidParseError("File not found")

    pages = _read_pages(resolved)
    if not pages:
        raise BidParseError("PDF has no pages")

    kinds = {page["page"]: _classify(page) for page in pages}
    flagged = [{"page": number, "kind": kind}
               for number, kind in kinds.items() if kind != "text"]
    lines = [line.strip() for page in pages for line in page["text"].splitlines()
             if line.strip()]
    currency = _detect_currency(pages)

    try:
        strict = parse_bid(resolved, bids_dir)
    except PathOutsideError:
        raise
    except BidParseError:
        strict = None

    if strict is not None:
        items = _enrich_strict(strict, pages)
        stated = strict["stated_total"]
        computed, issues = strict["computed_total"], list(strict["issues"])
        subtotal = vat = None
        method = "strict"
        used = {item["page"] for item in items if item["page"]}
        total_page, _ = _page_of(pages, "Stated total")
        if total_page:
            used.add(total_page)
    else:
        text_pages = [number for number, kind in kinds.items() if kind == "text"]
        layout = _layout_pages(resolved, text_pages) if text_pages else {}
        parsed = _parse_layout_pages(layout)
        items = parsed["items"]
        subtotal, vat = parsed["subtotal"], parsed["vat"]
        stated = parsed["stated_total"]
        method = "table"
        used = parsed["used_pages"]
        total_page = parsed["stated_page"]

        if verified_rows:
            known = {item.get("source_text") for item in items}
            added = 0
            for row in verify_extracted_rows(
                    "\n".join(page["text"] for page in pages), verified_rows)["accepted"]:
                if row.get("source_text") in known:
                    continue
                items.append({
                    "no": int(row.get("no") or len(items) + 1),
                    "item_label": str(row.get("item_label") or len(items) + 1),
                    "description": row["description"],
                    "unit": row.get("unit", ""),
                    "quantity": row["quantity"],
                    "unit_price": row["unit_price"],
                    "line_total": row["line_total"],
                    "page": row.get("page"),
                    "source_text": row.get("source_text"),
                })
                added += 1
            if added:
                method = "model_verified"

        computed, issues = _reconcile(items, vat)

    if stated is not None and abs(stated - computed) > 0.01:
        issues.append(f"Stated total {stated:.2f} does not match computed total {computed:.2f}")
    arithmetic_ok = stated is not None and not issues

    bidder = _labelled(lines, "Bidder")
    tender_ref = _labelled(lines, "Tender reference", "Tender ref", "Tender No.")

    if not items and stated is None:
        status = "unreadable"
    elif not items or stated is None or currency != "KES":
        status = "needs_review"
    else:
        status = "ok"

    if status == "ok":
        confidence = "medium" if flagged else "high"
    else:
        confidence = "low"

    unresolved = [
        {"page": page["page"], "text": page["text"]}
        for page in pages if kinds[page["page"]] == "text" and page["page"] not in used
    ]

    return {
        "bidder": bidder,
        "file": resolved.name,
        "total_page": total_page,
        "tender_ref": tender_ref,
        "currency": currency,
        "items": items,
        "subtotal": subtotal,
        "vat": vat,
        "stated_total": stated,
        "computed_total": computed,
        "arithmetic_ok": arithmetic_ok,
        "issues": issues,
        "confidence": confidence,
        "status": status,
        "method": method,
        "flagged_pages": flagged,
        "unresolved_pages": unresolved,
    }


def extract_bid_pdf(path: str, verified_rows: list[dict] | None = None) -> dict:
    """MCP wrapper for extract_bid."""
    return extract_bid(Path(path), settings.bids_dir, verified_rows)
