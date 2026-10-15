import pytest
from copy import deepcopy

from mcp_server.tools.benchmark_price import benchmark, benchmark_price

MIN_N = 5
HIGH_N = 15
FAR_PCT = 50


def pool_of(n, start=1):
    """A clean pool of n awards with values 1..n millions."""
    return [{"award_id": f"a{i:02d}", "value_kes": float(i * 1_000_000)} for i in range(start, start + n)]


def test_known_pool_gives_exact_median_and_quartiles():
    pool = pool_of(5)
    result = benchmark([{"bidder": "Apex", "total": 3_000_000.0}], pool, MIN_N, HIGH_N, FAR_PCT)

    assert result["n"] == 5
    assert result["confidence"] == "medium"
    assert result["median_kes"] == 3_000_000.0
    assert result["q1_kes"] == 2_000_000.0
    assert result["q3_kes"] == 4_000_000.0


@pytest.mark.parametrize(
    "total, expected",
    [
        (5_000_000.0, "far_above"),
        (4_500_000.0, "above_range"),
        (4_000_000.0, "within_range"),
        (3_000_000.0, "within_range"),
        (2_000_000.0, "within_range"),
        (1_500_000.0, "below_range"),
        (1_000_000.0, "far_below"),
    ],
)
def test_positions_including_boundaries(total, expected):
    pool = pool_of(5)
    result = benchmark([{"bidder": "Apex", "total": total}], pool, MIN_N, HIGH_N, FAR_PCT)

    assert result["bids"][0]["position"] == expected


def test_pct_vs_median_rounded_to_one_decimal():
    pool = pool_of(5)
    bids = [{"bidder": "Apex", "total": 5_000_000.0}, {"bidder": "Bora", "total": 1_000_000.0}]
    result = benchmark(bids, pool, MIN_N, HIGH_N, FAR_PCT)

    assert result["bids"][0]["pct_vs_median"] == 66.7
    assert result["bids"][1]["pct_vs_median"] == -66.7


@pytest.mark.parametrize(
    "n, expected",
    [(4, "insufficient"), (5, "medium"), (14, "medium"), (15, "high")],
)
def test_confidence_at_the_boundaries(n, expected):
    result = benchmark([{"bidder": "Apex", "total": 3_000_000.0}], pool_of(n), MIN_N, HIGH_N, FAR_PCT)

    assert result["confidence"] == expected


def test_insufficient_returns_nulls_and_still_lists_sources():
    pool = pool_of(4)
    result = benchmark([{"bidder": "Apex", "total": 3_000_000.0}], pool, MIN_N, HIGH_N, FAR_PCT)

    assert result["n"] == 4
    assert result["confidence"] == "insufficient"
    assert result["median_kes"] is None
    assert result["q1_kes"] is None
    assert result["q3_kes"] is None
    assert result["bids"][0]["pct_vs_median"] is None
    assert result["bids"][0]["position"] is None
    assert result["sources"] == ["a01", "a02", "a03", "a04"]


def test_one_huge_value_does_not_move_the_median():
    small = [{"award_id": f"a{i:02d}", "value_kes": float(i * 1_000_000)} for i in range(1, 10)]
    huge_pool = small + [{"award_id": "a99", "value_kes": 900_000_000_000.0}]
    bigger_pool = small + [{"award_id": "a99", "value_kes": 900_000_000_000_000_000.0}]
    bids = [{"bidder": "Apex", "total": 5_000_000.0}]

    huge = benchmark(bids, huge_pool, MIN_N, HIGH_N, FAR_PCT)
    bigger = benchmark(bids, bigger_pool, MIN_N, HIGH_N, FAR_PCT)

    assert huge["n"] == bigger["n"] == 10
    assert huge["median_kes"] == bigger["median_kes"] == 5_500_000.0


def test_sources_sorted_and_unique_inputs_unchanged_bid_order_kept():
    pool = [
        {"award_id": "c3", "value_kes": 3_000_000.0, "supplier_name": "keep"},
        {"award_id": "a1", "value_kes": 1_000_000.0, "supplier_name": "keep"},
        {"award_id": "c3", "value_kes": 3_000_000.0, "supplier_name": "keep"},
        {"award_id": "b2", "value_kes": 2_000_000.0, "supplier_name": "keep"},
        {"award_id": "a0", "value_kes": 4_000_000.0, "supplier_name": "keep"},
    ]
    bids = [
        {"bidder": "Zed", "total": 2_500_000.0},
        {"bidder": "Apex", "total": 9_000_000.0},
        {"bidder": "Bora", "total": 500_000.0},
    ]
    pool_before = deepcopy(pool)
    bids_before = deepcopy(bids)

    result = benchmark(bids, pool, MIN_N, HIGH_N, FAR_PCT)

    assert result["sources"] == ["a0", "a1", "b2", "c3"]
    assert [b["bidder"] for b in result["bids"]] == ["Zed", "Apex", "Bora"]
    assert pool == pool_before
    assert bids == bids_before


@pytest.mark.parametrize(
    "bids, pool, expected",
    [
        ([{"total": 3_000_000.0}], [{"award_id": "a1", "value_kes": 1.0}], "bidder"),
        ([{"bidder": "Apex"}], [{"award_id": "a1", "value_kes": 1.0}], "total"),
        ([{"bidder": "Apex", "total": 0.0}], [{"award_id": "a1", "value_kes": 1.0}], "total"),
        ([{"bidder": "Apex", "total": -5.0}], [{"award_id": "a1", "value_kes": 1.0}], "total"),
        ([{"bidder": "Apex", "total": 3_000_000.0}], [{"award_id": "a1", "value_kes": 0.0}], "value_kes"),
        ([{"bidder": "Apex", "total": 3_000_000.0}], [{"award_id": "a1", "value_kes": -1.0}], "value_kes"),
        ([{"bidder": "Apex", "total": 3_000_000.0}], [{"value_kes": 1.0}], "award_id"),
        ([], [{"award_id": "a1", "value_kes": 1.0}], "bids"),
    ],
)
def test_validation_errors_name_the_field(bids, pool, expected):
    with pytest.raises(ValueError) as err:
        benchmark(bids, pool, MIN_N, HIGH_N, FAR_PCT)

    assert expected in str(err.value)


def test_wrapper_uses_settings_thresholds():
    pool = pool_of(20)
    bids = [{"bidder": "Apex", "total": 3_000_000.0}]

    wrapped = benchmark_price(bids, pool)
    direct = benchmark(bids, pool, MIN_N, HIGH_N, FAR_PCT)

    assert wrapped == direct
    assert wrapped["confidence"] == "high"
