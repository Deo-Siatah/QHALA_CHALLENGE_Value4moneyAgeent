import os
import psycopg
from dotenv import load_dotenv

load_dotenv()
QUERIES = [
    ("Value spread inside the 6 biggest lot groups (count, min, median, max)",
     """SELECT lot_group, count(*), min(value_kes), 
               percentile_cont(0.5) WITHIN GROUP (ORDER BY value_kes)::numeric(14,0),
               max(value_kes)
        FROM awards WHERE lot_group IS NOT NULL AND value_kes > 0
        GROUP BY 1 ORDER BY 2 DESC LIMIT 6"""),
    ("Awards with value > 0 matching a keyword in the tender title",
     """SELECT k, count(*) FROM (VALUES ('road'),('classroom'),('pole | poles'),
        ('transformer'),('pipe | pipes'),('laptop | laptops'),('uniform | uniforms')) w(k)
        JOIN tenders t ON to_tsvector('simple', coalesce(t.title,'')) @@ to_tsquery('simple', w.k)
        JOIN awards a ON a.ocid = t.ocid AND a.value_kes > 0
        GROUP BY k ORDER BY 2 DESC"""),
    ("Awards by procurement method",
     """SELECT t.method, count(*) FROM awards a JOIN tenders t USING (ocid)
        GROUP BY 1 ORDER BY 2 DESC"""),
    ("Table sizes (including indexes)",
     """SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
        FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC"""),
]

with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    for label, q in QUERIES:
        print(f"\n-- {label}")
        for row in conn.execute(q).fetchall():
            print("  ", row)