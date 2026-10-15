# Get a psycopg connection from settings.database_url, rows as dicts.
# Clear error if the URL is unset. Nothing else.

import psycopg
from psycopg.rows import dict_row
from config import settings

def get_conn():
    """Get a psycopg connection from settings.database_url, rows as dicts."""
    if not settings.database_url:
        raise ValueError("DATABASE_URL is not set")
    return psycopg.connect(settings.database_url, row_factory=dict_row)