# Find candidate past awards for a described job. It only retrieves.
# Judging similarity is the model's job later, price statistics are tool 4.
# It must be easy to widen step by step, because the research loop retries with looser settings.

import re
from typing import Optional, List, Dict, Any
from psycopg import sql, errors
from psycopg.rows import dict_row
from config import settings
from ..db import get_conn

def _sanitize_query(query: str) -> List[str]:
    """Turn query into tokens: lowercase, keep [a-z0-9]+, drop short tokens and stoplist."""
    stoplist = {'the', 'and', 'or', 'of', 'in', 'to', 'for', 'with', 'by', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'at', 'as', 'on', 'that', 'this', 'it', 'proposed'}
    
    # Keep only alphanumeric characters, lowercase
    tokens = re.findall(r'[a-z0-9]+', query.lower())
    
    # Filter out short tokens and stoplist
    tokens = [token for token in tokens if len(token) >= 3 and token not in stoplist]
    
    if not tokens:
        raise ValueError("No usable tokens found in query")
    
    return tokens

def search_awards(conn, query: str, category: Optional[str] = None, buyer_id: Optional[str] = None, 
                  match: str = "strict", min_year: Optional[int] = None, 
                  exclude_ocid: Optional[str] = None, limit: int = 30, 
                  fuzzy_threshold: float = 0.3) -> dict:
    """Search for awards matching the query with specified matching criteria."""
    
    # Validate parameters
    if match not in ["strict", "loose", "fuzzy"]:
        raise ValueError(f"match must be 'strict', 'loose', or 'fuzzy', got '{match}'")
    
    if category is not None and category not in ["works", "goods", "services"]:
        raise ValueError(f"category must be 'works', 'goods', or 'services', got '{category}'")
    
    # Sanitize query and get tokens
    tokens = _sanitize_query(query)
    
    # Build WHERE clause conditions
    conditions = ["a.value_kes > 0", "a.currency = 'KES'"]
    filter_params = []
    
    if category:
        conditions.append("t.category = %s")
        filter_params.append(category)
    
    if buyer_id:
        conditions.append("t.buyer_id = %s")
        filter_params.append(buyer_id)
    
    if min_year:
        conditions.append("a.data_year >= %s")
        filter_params.append(min_year)
    
    if exclude_ocid:
        conditions.append("a.ocid <> %s")
        filter_params.append(exclude_ocid)
    
    # Build query based on match type
    if match == "strict":
        # Every token must appear
        tsquery = " & ".join(tokens)
        where_clause = conditions + [f"to_tsvector('simple', coalesce(t.title, '')) @@ to_tsquery('simple', %s)"]
        filter_params.append(tsquery)
        rank_expr = "ts_rank(to_tsvector('simple', coalesce(t.title, '')), to_tsquery('simple', %s))"
        rank_arg = tsquery
    
    elif match == "loose":
        # Any token may appear
        tsquery = " | ".join(tokens)
        where_clause = conditions + [f"to_tsvector('simple', coalesce(t.title, '')) @@ to_tsquery('simple', %s)"]
        filter_params.append(tsquery)
        rank_expr = "ts_rank(to_tsvector('simple', coalesce(t.title, '')), to_tsquery('simple', %s))"
        rank_arg = tsquery
    
    elif match == "fuzzy":
        # Use similarity with pg_trgm
        tokens_str = " ".join(tokens)
        where_clause = conditions + [f"similarity(lower(coalesce(t.title, '')), %s) >= %s"]
        filter_params.extend([tokens_str, fuzzy_threshold])
        rank_expr = "similarity(lower(coalesce(t.title, '')), %s)"
        rank_arg = tokens_str
    
    # Parameters follow the order the placeholders appear in the text: SELECT score, WHERE, ORDER BY, LIMIT
    params = [rank_arg] + filter_params + [rank_arg]
    order_clause = f"{rank_expr} DESC, a.data_year DESC, a.award_id ASC"
    
    # Build final query
    query_str = f"""
    SELECT a.award_id, a.ocid, a.data_year, t.title, t.buyer_name, t.category, t.method,
           a.value_kes, a.currency, a.supplier_name, a.supplier_norm, a.lot_group,
           a.quality_flags as flags,
           {rank_expr} as score
    FROM awards a
    JOIN tenders t ON a.ocid = t.ocid
    WHERE {' AND '.join(where_clause)}
    ORDER BY {order_clause}
    LIMIT %s
    """
    
    params.append(limit)
    
    # Execute query
    with conn.cursor() as cur:
        cur.execute(query_str, params)
        candidates = cur.fetchall()
    
    # Prepare filters for output
    filters = {
        "query": tokens,
        "match": match,
        "category": category,
        "buyer_id": buyer_id,
        "min_year": min_year,
        "exclude_ocid": exclude_ocid,
        "limit": limit
    }
    
    # Merge tender and award flags
    for candidate in candidates:
        if candidate.get("flags"):
            candidate["flags"] = candidate["flags"].split(",") if isinstance(candidate["flags"], str) else candidate["flags"]
        else:
            candidate["flags"] = []
    
    return {
        "filters": filters,
        "count": len(candidates),
        "candidates": candidates
    }

def find_comparable_awards(query: str, category: Optional[str] = None, buyer_id: Optional[str] = None, 
                          match: str = "strict", min_year: Optional[int] = None, 
                          exclude_ocid: Optional[str] = None) -> dict:
    """Wrapper MCP tool for finding comparable awards."""
    conn = get_conn()
    try:
        return search_awards(
            conn, query, category, buyer_id, match, min_year, exclude_ocid,
            limit=settings.max_candidates, fuzzy_threshold=settings.fuzzy_threshold
        )
    finally:
        conn.close()