# Place each bid total against the final comparable pool. Pure, no database.
# It uses the median, never the mean, and quartiles for the normal range.
# Each bid gets one number: how far from the median, and which band it falls in.
# Below the minimum number of comparables it returns only the count: no labels, no guessing.

from typing import Any, Dict, List
from statistics import median, quantiles
from config import settings


def _positive(value: Any) -> bool:
    """True when a value is a real number above zero."""
    return not isinstance(value, bool) and isinstance(value, (int, float)) and value > 0


def _checked_bids(bids: List[Dict[str, Any]]) -> List[tuple]:
    """Check each bid has a bidder name and a positive total, and keep them in input order."""
    if not bids:
        raise ValueError("bids is empty: at least one bid is needed to benchmark")
    checked = []
    for i, bid in enumerate(bids):
        bidder = bid.get("bidder")
        if not isinstance(bidder, str) or not bidder.strip():
            raise ValueError(f"bids[{i}].bidder is missing or empty")
        if not _positive(bid.get("total")):
            raise ValueError(f"bids[{i}].total must be a number above 0, got {bid.get('total')!r} ({bidder})")
        checked.append((bidder, float(bid["total"])))
    return checked


def _check_pool(pool: List[Dict[str, Any]]) -> None:
    """Check each pool row has an award_id and a positive value_kes, so it can be cited."""
    for i, item in enumerate(pool):
        award_id = item.get("award_id")
        if not isinstance(award_id, str) or not award_id.strip():
            raise ValueError(f"pool[{i}].award_id is missing or empty")
        if not _positive(item.get("value_kes")):
            raise ValueError(f"pool[{i}].value_kes must be a number above 0, got {item.get('value_kes')!r} ({award_id})")


def _position(total: float, med: float, q1: float, q3: float, far_pct: float) -> str:
    """Name the band a total falls in: far off first, then the quartile range."""
    pct = round((total - med) / med * 100, 1)
    if pct > far_pct:
        return "far_above"
    if pct < -far_pct:
        return "far_below"
    if q1 <= total <= q3:
        return "within_range"
    return "above_range" if total > q3 else "below_range"


def benchmark(bids: List[Dict[str, Any]], pool: List[Dict[str, Any]], min_comparables: int,
              high_confidence_n: int, far_pct: float) -> dict:
    """Benchmark bid totals against a comparable pool with plain statistics."""
    checked = _checked_bids(bids)
    _check_pool(pool)

    n = len(pool)
    sources = sorted({item["award_id"] for item in pool})
    empty = {"median_kes": None, "q1_kes": None, "q3_kes": None}
    if n < min_comparables or n < 2:
        return {"n": n, "confidence": "insufficient", **empty, "sources": sources,
                "bids": [{"bidder": b, "total": round(t, 2), "pct_vs_median": None, "position": None}
                         for b, t in checked]}

    values = sorted(float(item["value_kes"]) for item in pool)
    med = median(values)
    q1, _, q3 = quantiles(values, n=4, method="inclusive")
    rows = []
    for bidder, total in checked:
        rows.append({"bidder": bidder, "total": round(total, 2),
                     "pct_vs_median": round((total - med) / med * 100, 1),
                     "position": _position(total, med, q1, q3, far_pct)})
    return {"n": n, "confidence": "high" if n >= high_confidence_n else "medium",
            "median_kes": round(med, 2), "q1_kes": round(q1, 2), "q3_kes": round(q3, 2),
            "sources": sources, "bids": rows}


def benchmark_price(bids: List[Dict[str, Any]], pool: List[Dict[str, Any]]) -> dict:
    """Benchmark bid totals using the thresholds from settings."""
    return benchmark(bids, pool, settings.min_comparables, settings.high_confidence_n,
                     settings.far_from_median_pct)
