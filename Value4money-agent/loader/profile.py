import sys, pathlib
import pandas as pd

year = sys.argv[1]
d = pathlib.Path("data/raw") / year
rd = lambda n: pd.read_csv(d / f"{n}.csv", dtype=str, encoding="utf-8-sig")
main, awards, contracts, sup = rd("main"), rd("awards"), rd("contracts"), rd("awards_suppliers")

for name, df in [("main", main), ("awards", awards), ("contracts", contracts), ("awards_suppliers", sup)]:
    print(f"\n== {name}: {len(df):,} rows")
    print(list(df.columns))

print("\n== value-like columns in main:", [c for c in main.columns if "value" in c.lower()])
print("\n== category:\n", main.tender_mainProcurementCategory.value_counts(dropna=False))
print("\n== method:\n", main.tender_procurementMethod.value_counts(dropna=False))

a_ocids, t_ocids = set(awards.main_ocid), set(main.ocid)
print("\n== JOIN COVERAGE")
print("tenders:", len(t_ocids), "| tenders with an award:", len(t_ocids & a_ocids))
print("awards with no matching tender:", len(a_ocids - t_ocids))
print("tenders with more than 1 award row:", int((awards.groupby("main_ocid").size() > 1).sum()))
print("awards with more than 1 supplier:", int((sup.groupby("awards_id").size() > 1).sum()))
print("awards with no supplier:", len(set(awards.id) - set(sup.awards_id)))

awards["v"] = pd.to_numeric(awards.value_amount, errors="coerce")
print("\n== VALUES")
print("non-KES awards:", int((awards.value_currency != "KES").sum()))
print("null or <= 0 values:", int((awards.v.isna() | (awards.v <= 0)).sum()))
print("5 largest:", awards.v.nlargest(5).tolist())
print("median:", awards.v.median())

c = contracts.merge(awards[["id", "v"]], left_on="awardID", right_on="id")
c["cv"] = pd.to_numeric(c.value_amount, errors="coerce")
print("contract value differs from award value:", int((c.cv != c.v).sum()), "of", len(c))

s = pd.to_datetime(main.tender_tenderPeriod_startDate, utc=True, errors="coerce")
e = pd.to_datetime(main.tender_tenderPeriod_endDate, utc=True, errors="coerce")
print("\n== DATES")
print("tender start after end:", int((s > e).sum()), "of", len(main))
print("unparseable dates:", int(s.isna().sum()), int(e.isna().sum()))