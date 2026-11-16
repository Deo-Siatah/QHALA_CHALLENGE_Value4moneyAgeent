# Find candidate past awards for a described job. It only retrieves.
# Judging similarity is the model's job later, price statistics are tool 4.
# It must be easy to widen step by step, because the research loop retries with looser settings.
# Core terms are the words that name the work itself. They are required on every attempt, so
# widening the match mode can never turn a classroom-block pool into a road or a pit-latrine pool.

import re
from typing import Optional, List, Dict, Any
from config import settings
from ..db import get_conn


def _sanitize_query(query: str) -> List[str]:
    """Turn query into tokens: lowercase, keep [a-z0-9]+, drop short tokens and stoplist."""
    stoplist = {'the', 'and', 'or', 'of', 'in', 'to', 'for', 'with', 'by', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'at', 'as', 'on', 'that', 'this', 'it', 'proposed'}
    tokens = re.findall(r'[a-z0-9]+', query.lower())
    tokens = [token for token in tokens if len(token) >= 3 and token not in stoplist]
    if not tokens:
        raise ValueError("No usable tokens found in query")
    return tokens


def _core_terms(required_terms: Optional[List[str]]) -> List[str]:
    """Normalise the required core terms, dropping duplicates and unusable words."""
    stoplist = {'the', 'and', 'or', 'of', 'in', 'to', 'for', 'with', 'by', 'a', 'an'}
    terms: List[str] = []
    for term in required_terms or []:
        for token in re.findall(r'[a-z0-9]+', str(term).lower()):
            if len(token) >= 3 and token not in stoplist and token not in terms:
                terms.append(token)
    return terms


def search_awards(conn, query: str, category: Optional[str] = None, buyer_id: Optional[str] = None,
                  match: str = "strict", min_year: Optional[int] = None,
                  exclude_ocid: Optional[str] = None, limit: int = 30,
                  fuzzy_threshold: float = 0.3,
                  required_terms: Optional[List[str]] = None) -> dict:
    """Search for awards matching the query with specified matching criteria."""

    if match not in ["strict", "loose", "fuzzy"]:
        raise ValueError(f"match must be 'strict', 'loose', or 'fuzzy', got '{match}'")

    if category is not None and category not in ["works", "goods", "services"]:
        raise ValueError(f"category must be 'works', 'goods', or 'services', got '{category}'")

    tokens = _sanitize_query(query)
    core = _core_terms(required_terms)

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

    for term in core:
        if match == "fuzzy":
            conditions.append("lower(coalesce(t.title, '')) LIKE %s")
            filter_params.append(f"{term}%")
        else:
            conditions.append("to_tsvector('simple', coalesce(t.title, '')) @@ to_tsquery('simple', %s)")
            filter_params.append(f"{term}:*")

    if match == "strict":
        tsquery = " & ".join(tokens)
        where_clause = conditions + ["to_tsvector('simple', coalesce(t.title, '')) @@ to_tsquery('simple', %s)"]
        filter_params.append(tsquery)
        rank_expr = "ts_rank(to_tsvector('simple', coalesce(t.title, '')), to_tsquery('simple', %s))"
        rank_arg = tsquery

    elif match == "loose":
        tsquery = " | ".join(tokens)
        where_clause = conditions + ["to_tsvector('simple', coalesce(t.title, '')) @@ to_tsquery('simple', %s)"]
        filter_params.append(tsquery)
        rank_expr = "ts_rank(to_tsvector('simple', coalesce(t.title, '')), to_tsquery('simple', %s))"
        rank_arg = tsquery

    else:
        tokens_str = " ".join(tokens)
        where_clause = conditions + ["similarity(lower(coalesce(t.title, '')), %s) >= %s"]
        filter_params.extend([tokens_str, fuzzy_threshold])
        rank_expr = "similarity(lower(coalesce(t.title, '')), %s)"
        rank_arg = tokens_str

    params = [rank_arg] + filter_params + [rank_arg]
    order_clause = f"{rank_expr} DESC, a.data_year DESC, a.award_id ASC"

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

    with conn.cursor() as cur:
        cur.execute(query_str, params)
        candidates = cur.fetchall()

    filters = {
        "query": tokens,
        "required_terms": core,
        "match": match,
        "category": category,
        "buyer_id": buyer_id,
        "min_year": min_year,
        "exclude_ocid": exclude_ocid,
        "limit": limit
    }

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
                          exclude_ocid: Optional[str] = None,
                          required_terms: Optional[List[str]] = None) -> dict:
    """Wrapper MCP tool for finding comparable awards."""
    conn = get_conn()
    try:
        return search_awards(
            conn, query, category, buyer_id, match, min_year, exclude_ocid,
            limit=settings.max_candidates, fuzzy_threshold=settings.fuzzy_threshold,
            required_terms=required_terms
        )
    finally:
        conn.close()
