"""Load Kenya OCDS CSV exports (main, awards, awards_suppliers) into Postgres.

  uv run python loader/load.py --years 2026 --dry-run
  uv run python loader/load.py --years 2024 2025 2026
"""
import argparse
import os
import pathlib
import re
import sys
from collections import Counter

import ftfy
import numpy as np
import pandas as pd

ALLOWED_METHODS = {"open", "selective", "direct"}
STOP_WORDS = {"limited", "ltd", "company", "co", "plc", "inc"}
REF_RE = re.compile(r"^ocds-[a-z0-9]+-\d+-(.+)$", re.I)
LOT_RE = re.compile(r"^(.*)-(\d{1,3})$")

T_COLS = ["ocid", "data_year", "buyer_id", "buyer_name", "title", "category",
          "method", "published_at", "flags"]
A_COLS = ["award_id", "ocid", "data_year", "award_title", "award_description",
          "value_kes", "currency", "contract_start", "contract_end",
          "supplier_name", "supplier_norm", "lot_group", "flags"]


# ---------- helpers ----------
def clean_text(x):
    if pd.isna(x):
        return None
    s = ftfy.fix_text(str(x)).replace("\x00", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def read(d, name):
    p = d / f"{name}.csv"
    if not p.exists():
        sys.exit(f"Missing file: {p}")
    return pd.read_csv(p, dtype=str, encoding="utf-8-sig",
                       keep_default_na=False, na_values=[""])


def col(df, name):
    """Column by name, or an empty column if this year's file doesn't have it."""
    if name in df.columns:
        return df[name]
    return pd.Series([None] * len(df), index=df.index, dtype=object)


def to_ts(series):
    return pd.to_datetime(series, errors="coerce", utc=True)


def local_date(series):
    t = to_ts(series).dt.tz_convert("Africa/Nairobi")
    return t.map(lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else None)


def add_flag(flags, mask, name):
    for i in np.flatnonzero(np.asarray(mask, dtype=bool)):
        flags[i].append(name)


def norm_supplier(name):
    if name is None or pd.isna(name):
        return None
    s = re.sub(r"[^a-z0-9 ]+", " ", name.lower())
    toks = [w for w in s.split() if w not in STOP_WORDS]
    return " ".join(toks) or None


def lot_group(ocid, buyer_id):
    """Siblings share a reference that differs only in a trailing lot number,
    e.g. KeRRA/08/MDR/39/25/26-049 and ...-051. Best effort; None if no pattern."""
    m = REF_RE.match(ocid or "")
    if not m:
        return None
    ref = m.group(1)
    if "/" not in ref:
        return None
    m2 = LOT_RE.match(ref)
    if not m2:
        return None
    prefix = m2.group(1)
    if len(prefix) < 8 or re.search(r"(19|20)\d{2}$", prefix):
        return None  # looks like a financial-year range, not a lot number
    b = buyer_id if isinstance(buyer_id, str) and buyer_id else "x"
    return f"{b}:{prefix}"


# ---------- transforms ----------
def build_tenders(main, year):
    t = pd.DataFrame({
        "ocid": col(main, "ocid").map(clean_text),
        "data_year": str(year),
        "buyer_id": col(main, "buyer_id").map(clean_text),
        "buyer_name": col(main, "buyer_name").map(clean_text),
        "title": col(main, "tender_title").map(clean_text),
        "category": col(main, "tender_mainProcurementCategory").map(clean_text),
        "method": col(main, "tender_procurementMethod").map(clean_text),
        "published_at": to_ts(col(main, "date")),
    })
    t = (t.dropna(subset=["ocid"])
          .sort_values("published_at")
          .drop_duplicates("ocid", keep="last")
          .reset_index(drop=True))
    t["category"] = t.category.str.lower()
    t["method"] = t.method.str.lower()

    flags = [[] for _ in range(len(t))]
    add_flag(flags, t.category.isna(), "no_category")
    add_flag(flags, t.method.notna() & ~t.method.isin(ALLOWED_METHODS), "unusual_method")
    add_flag(flags, t.published_at.isna(), "bad_date")
    add_flag(flags, t.title.isna(), "no_title")
    t["flags"] = [",".join(f) for f in flags]
    t["published_at"] = t.published_at.map(lambda x: x.isoformat() if pd.notna(x) else None)
    return t


def build_awards(awards, sup, tenders, year):
    a = pd.DataFrame({
        "award_id": col(awards, "id").map(clean_text),
        "ocid": col(awards, "main_ocid").map(clean_text),
        "award_title": col(awards, "title").map(clean_text),
        "award_description": col(awards, "description").map(clean_text),
        "currency": col(awards, "value_currency").map(clean_text),
        "raw_value": col(awards, "value_amount").map(clean_text),
        "contract_start": local_date(col(awards, "contractPeriod_startDate")),
        "contract_end": local_date(col(awards, "contractPeriod_endDate")),
    })
    a = a.dropna(subset=["award_id", "ocid"]).drop_duplicates("award_id", keep="last")
    known = a.ocid.isin(tenders.ocid)
    orphans = int((~known).sum())
    a = a[known].copy()

    s = pd.DataFrame({
        "award_id": col(sup, "awards_id").map(clean_text),
        "supplier_name": col(sup, "name").map(clean_text),
    }).dropna(subset=["award_id"]).drop_duplicates("award_id", keep="first")

    a = a.merge(s, on="award_id", how="left")
    a = a.merge(tenders[["ocid", "buyer_id"]], on="ocid", how="left")

    num = pd.to_numeric(a.raw_value, errors="coerce")
    a["value_kes"] = a.raw_value.where(num.notna(), None)
    a["data_year"] = str(year)
    a["supplier_norm"] = a.supplier_name.map(norm_supplier)
    a["lot_group"] = [lot_group(o, b) for o, b in zip(a.ocid, a.buyer_id)]

    flags = [[] for _ in range(len(a))]
    add_flag(flags, num.isna() | (num <= 0), "non_positive_value")
    add_flag(flags, a.currency.notna() & (a.currency != "KES"), "non_kes")
    add_flag(flags, a.supplier_name.isna(), "no_supplier")
    add_flag(flags, a.contract_start.notna() & a.contract_end.notna()
             & (a.contract_end < a.contract_start), "bad_contract_dates")
    add_flag(flags, a.duplicated(["ocid", "raw_value"], keep=False) & (num > 0),
             "same_value_in_tender")
    a["flags"] = [",".join(f) for f in flags]
    return a.reset_index(drop=True), orphans


# ---------- database ----------
UPSERT_TENDERS = """
INSERT INTO tenders (ocid, data_year, buyer_id, buyer_name, title, category,
                     method, published_at, quality_flags)
SELECT ocid, data_year::int, buyer_id, buyer_name, title, category, method,
       published_at::timestamptz,
       CASE WHEN flags = '' THEN '{}'::text[] ELSE string_to_array(flags, ',') END
FROM stg_tenders
ON CONFLICT (ocid) DO UPDATE SET
  data_year = EXCLUDED.data_year, buyer_id = EXCLUDED.buyer_id,
  buyer_name = EXCLUDED.buyer_name, title = EXCLUDED.title,
  category = EXCLUDED.category, method = EXCLUDED.method,
  published_at = EXCLUDED.published_at, quality_flags = EXCLUDED.quality_flags
"""

UPSERT_AWARDS = """
INSERT INTO awards (award_id, ocid, data_year, award_title, award_description,
                    value_kes, currency, contract_start, contract_end,
                    supplier_name, supplier_norm, lot_group, quality_flags)
SELECT award_id, ocid, data_year::int, award_title, award_description,
       value_kes::numeric, currency, contract_start::date, contract_end::date,
       supplier_name, supplier_norm, lot_group,
       CASE WHEN flags = '' THEN '{}'::text[] ELSE string_to_array(flags, ',') END
FROM stg_awards
ON CONFLICT (award_id) DO UPDATE SET
  ocid = EXCLUDED.ocid, data_year = EXCLUDED.data_year,
  award_title = EXCLUDED.award_title, award_description = EXCLUDED.award_description,
  value_kes = EXCLUDED.value_kes, currency = EXCLUDED.currency,
  contract_start = EXCLUDED.contract_start, contract_end = EXCLUDED.contract_end,
  supplier_name = EXCLUDED.supplier_name, supplier_norm = EXCLUDED.supplier_norm,
  lot_group = EXCLUDED.lot_group, quality_flags = EXCLUDED.quality_flags
"""


def copy_rows(cur, table, cols, df):
    with cur.copy(f"COPY {table} ({', '.join(cols)}) FROM STDIN") as cp:
        for r in df[cols].itertuples(index=False, name=None):
            cp.write_row([None if pd.isna(v) else v for v in r])


def load_year(conn, year, t, a, n_sup):
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("CREATE TEMP TABLE stg_tenders (ocid text, data_year text, "
                        "buyer_id text, buyer_name text, title text, category text, "
                        "method text, published_at text, flags text) ON COMMIT DROP")
            cur.execute("CREATE TEMP TABLE stg_awards (award_id text, ocid text, "
                        "data_year text, award_title text, award_description text, "
                        "value_kes text, currency text, contract_start text, "
                        "contract_end text, supplier_name text, supplier_norm text, "
                        "lot_group text, flags text) ON COMMIT DROP")
            copy_rows(cur, "stg_tenders", T_COLS, t)
            cur.execute(UPSERT_TENDERS)
            copy_rows(cur, "stg_awards", A_COLS, a)
            cur.execute(UPSERT_AWARDS)
            for name, n in [("main.csv", len(t)), ("awards.csv", len(a)),
                            ("awards_suppliers.csv", n_sup)]:
                cur.execute("INSERT INTO load_log (year, file_name, rows_loaded) "
                            "VALUES (%s, %s, %s)", (year, name, n))


def summary(conn):
    queries = [
        ("tenders per year", "SELECT data_year, count(*) FROM tenders GROUP BY 1 ORDER BY 1"),
        ("awards per year (total, value > 0)",
         "SELECT data_year, count(*), count(*) FILTER (WHERE value_kes > 0) "
         "FROM awards GROUP BY 1 ORDER BY 1"),
        ("quality flags",
         "SELECT f, count(*) FROM (SELECT unnest(quality_flags) f FROM awards "
         "UNION ALL SELECT unnest(quality_flags) FROM tenders) x GROUP BY f ORDER BY 2 DESC"),
        ("awards with a lot_group", "SELECT count(*) FILTER (WHERE lot_group IS NOT NULL), "
         "count(*) FROM awards"),
        ("biggest lot groups", "SELECT lot_group, count(*) FROM awards "
         "WHERE lot_group IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 5"),
    ]
    with conn.cursor() as cur:
        for label, q in queries:
            cur.execute(q)
            print(f"\n-- {label}")
            for row in cur.fetchall():
                print("  ", row)


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="+", type=int, required=True)
    ap.add_argument("--data-dir", default="data/raw")
    ap.add_argument("--dry-run", action="store_true",
                    help="clean and report, but do not touch the database")
    args = ap.parse_args()

    conn = None
    if not args.dry_run:
        from dotenv import load_dotenv
        import psycopg
        load_dotenv()
        url = os.environ.get("DATABASE_URL")
        if not url:
            sys.exit("DATABASE_URL is not set (check your .env file)")
        conn = psycopg.connect(url, connect_timeout=30)

    for year in sorted(args.years):
        d = pathlib.Path(args.data_dir) / str(year)
        print(f"\n=== {year} ===")
        main_df, aw_df, sup_df = read(d, "main"), read(d, "awards"), read(d, "awards_suppliers")
        t = build_tenders(main_df, year)
        a, orphans = build_awards(aw_df, sup_df, t, year)
        n_sup = int(a.supplier_name.notna().sum())
        print(f"tenders: {len(t):,} | awards: {len(a):,} | awards with supplier: {n_sup:,} "
              f"| awards skipped (no matching tender): {orphans}")
        fc = Counter(f for s in pd.concat([t["flags"], a["flags"]]) for f in s.split(",") if f)
        print("flags:", dict(fc))
        print("with lot_group:", int(a.lot_group.notna().sum()),
              "| sample:", a.lot_group.dropna().drop_duplicates().head(3).tolist())
        if conn:
            load_year(conn, year, t, a, n_sup)
            print("loaded.")

    if conn:
        summary(conn)
        conn.close()
    else:
        print("\n(dry run: nothing written)")


if __name__ == "__main__":
    main()