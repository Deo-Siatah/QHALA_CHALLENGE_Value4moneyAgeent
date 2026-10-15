import os, sys, pathlib
import psycopg
from dotenv import load_dotenv

load_dotenv()
sql = pathlib.Path(sys.argv[1]).read_text()
with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    conn.execute(sql)
print("applied", sys.argv[1])