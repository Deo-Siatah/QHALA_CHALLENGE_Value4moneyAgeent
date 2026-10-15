# Cut a small, self-contained slice of the Kenya OCDS data and write it to sql/demo_data.sql.
#
# A stranger needs a benchmark pool before they can see the agent do anything useful, and the full
# exports are 55 MB of CSV they would otherwise have to find and download. This writes a slice of the
# tender and award records for four kinds of work instead: chainlink fence, road, classroom and
# borehole, which are the four the two sample bid sets are compared against.
#
# Run it with: uv run python -m loader.make_demo_slice
# It reads the DATABASE_URL you already have, and writes sql/demo_data.sql. Nothing is random and
# rows are sorted, so regenerating produces an identical file. The output carries only public tender
# data: no audit_log rows, no reports, no approver names.

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List

KEYWORDS = ["%chainlink%", "%fence%", "%road%", "%classroom%", "%borehole%"]

OUT_PATH = Path("sql/demo_data.sql")

TENDER_COLUMNS = ["ocid", "data_year", "buyer_id", "buyer_name", "title", "category", "method",
                  "published_at", "quality_flags"]

AWARD_COLUMNS = ["award_id", "ocid", "data_year", "award_title", "award_description", "value_kes",
                 "currency", "contract_start", "contract_end", "supplier_name", "supplier_norm",
                 "lot_group", "quality_flags"]

TENDER_SELECT = ("SELECT t.ocid, t.data_year, t.buyer_id, t.buyer_name, t.title, t.category, "
                 "t.method, t.published_at, t.quality_flags")

AWARD_SELECT = ("SELECT a.award_id, a.ocid, a.data_year, a.award_title, a.award_description, "
                "a.value_kes, a.currency, a.contract_start, a.contract_end, a.supplier_name, "
                "a.supplier_norm, a.lot_group, a.quality_flags")


def _any(keywords: List[str]) -> str:
    """The Postgres any() array of the keywords, quoted safely."""
    return "array[" + ", ".join("'" + k.replace("'", "''") + "'" for k in keywords) + "]"


def _match_clause(keywords: List[str]) -> str:
    """Both titles are searched, because a tender title and an award title say different things."""
    arr = _any(keywords)
    return (f"(t.title ILIKE ANY({arr}) OR a.award_title ILIKE ANY({arr}))")


def fetch_slice(conn: Any, keywords: List[str] = None) -> tuple:
    """Read the slice: every matching award, and the tenders those awards need."""
    keywords = KEYWORDS if keywords is None else keywords
    arr = _any(keywords)
    awards_sql = (AWARD_SELECT + " FROM awards a JOIN tenders t ON t.ocid = a.ocid "
                  f"WHERE a.value_kes > 0 AND {_match_clause(keywords)} ORDER BY a.award_id")
    tenders_sql = (TENDER_SELECT + " FROM tenders t WHERE EXISTS (SELECT 1 FROM awards a "
                   "WHERE a.ocid = t.ocid "
                   f"AND a.value_kes > 0 AND {_match_clause(keywords)}) ORDER BY t.ocid")
    awards = conn.execute(awards_sql).fetchall()
    tenders = conn.execute(tenders_sql).fetchall()
    return list(tenders), list(awards)


def literal(value: Any) -> str:
    """One value as SQL text: strings quoted, None left as NULL, arrays as arrays."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, datetime):
        return "'" + value.isoformat() + "'"
    if isinstance(value, date):
        return "'" + value.isoformat() + "'"
    if isinstance(value, (list, tuple)):
        if not value:
            return "'{}'::text[]"
        return "ARRAY[" + ", ".join(literal(str(item)) for item in value) + "]::text[]"
    return "'" + str(value).replace("'", "''") + "'"


def _statement(table: str, columns: List[str], rows: List[Dict[str, Any]],
               key: str) -> str:
    """One multi-row insert for one table, ordered by its key so the file never churns."""
    if not rows:
        return ""
    ordered = sorted(rows, key=lambda row: str(row.get(key)))
    columns_sql = ", ".join(columns)
    values = []
    for row in ordered:
        cells = ", ".join(literal(row.get(column)) for column in columns)
        values.append("  (" + cells + ")")
    return (f"INSERT INTO {table} ({columns_sql}) VALUES\n"
            + ",\n".join(values)
            + "\nON CONFLICT DO NOTHING;\n")


def render_sql(tenders: List[Dict[str, Any]], awards: List[Dict[str, Any]],
               source: str = "Kenya OCDS tender and award records") -> str:
    """The whole demo_data.sql file: header, then tenders before awards."""
    header = [
        "-- Demo slice of the " + source + ", public closed tenders only.",
        "-- Written by: uv run python -m loader.make_demo_slice",
        f"-- Contents: {len(tenders)} tenders, {len(awards)} awards.",
        "-- Covers chainlink fence, road, classroom and borehole work, which is what the sample bids",
        "-- in sample_bids/ and pdfs/ are compared against.",
        "-- Safe to apply to a database that already holds the full exports: every row is inserted",
        "-- only if it is missing.",
        "",
    ]
    body = (_statement("tenders", TENDER_COLUMNS, tenders, "ocid")
            + "\n"
            + _statement("awards", AWARD_COLUMNS, awards, "award_id"))
    return "\n".join(header) + body


def main() -> None:
    """Write the demo slice to sql/demo_data.sql."""
    from config import settings
    import psycopg
    from psycopg.rows import dict_row

    if not settings.database_url:
        raise SystemExit("DATABASE_URL is not set, so the demo slice cannot be cut. See .env.example.")

    with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
        tenders, awards = fetch_slice(conn)

    text = render_sql(tenders, awards)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {OUT_PATH} | {len(tenders)} tenders | {len(awards)} awards "
          f"| {len(text) / 1_000_000:.2f} MB")


if __name__ == "__main__":
    main()