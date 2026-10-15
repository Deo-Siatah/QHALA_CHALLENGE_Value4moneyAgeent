from mcp_server.tools.flag_data_quality import check_quality, flag_data_quality


def test_clean_pool_all_ok():
    """Test a clean pool: all ok, correct counts and median."""
    candidates = [
        {"award_id": "A1", "value_kes": 1000000, "currency": "KES"},
        {"award_id": "A2", "value_kes": 2000000, "currency": "KES"},
        {"award_id": "A3", "value_kes": 3000000, "currency": "KES"},
        {"award_id": "A4", "value_kes": 4000000, "currency": "KES"},
        {"award_id": "A5", "value_kes": 5000000, "currency": "KES"}
    ]
    
    result = check_quality(candidates)
    
    assert result["pool_size"] == 5
    assert result["median_kes"] == 3000000.0
    assert result["enough_comparables"] is True
    assert result["counts"] == {"ok": 5, "suspect": 0, "excluded": 0}
    assert len(result["results"]) == 5
    for r in result["results"]:
        assert r["verdict"] == "ok"
        assert r["ratio_to_median"] is not None


def test_missing_zero_negative_values_excluded():
    """Test missing, zero, negative values and non-KES are excluded with the right reason."""
    candidates = [
        {"award_id": "A1", "value_kes": 1000000, "currency": "KES"},  # Valid
        {"award_id": "A2", "value_kes": 0, "currency": "KES"},        # Zero value
        {"award_id": "A3", "value_kes": -100000, "currency": "KES"}, # Negative value
        {"award_id": "A4", "value_kes": 2000000, "currency": "USD"},  # Non-KES
        {"award_id": "A5", "value_kes": 3000000, "currency": "KES"},  # Valid
        {"award_id": "A6"},  # Missing value_kes
    ]
    
    result = check_quality(candidates)
    
    assert result["pool_size"] == 2  # A1 and A5 only
    assert result["counts"]["excluded"] == 4
    assert result["counts"]["ok"] == 2
    
    # Check excluded reasons
    excluded_reasons = []
    for r in result["results"]:
        if r["verdict"] == "excluded":
            excluded_reasons.extend(r["reasons"])
    
    assert "value_not_positive" in excluded_reasons
    assert "non_kes" in excluded_reasons


def test_duplicates():
    """Test duplicates: same ocid, value and supplier keeps the first and excludes the rest."""
    candidates = [
        {"award_id": "A1", "ocid": "t1", "value_kes": 1000000, "currency": "KES", "supplier_norm": "Supplier A"},
        {"award_id": "A2", "ocid": "t1", "value_kes": 1000000, "currency": "KES", "supplier_norm": "Supplier A"},  # Duplicate
        {"award_id": "A3", "ocid": "t1", "value_kes": 1000000, "currency": "KES", "supplier_norm": "Supplier B"},  # Different supplier
        {"award_id": "A4", "ocid": "t2", "value_kes": 1000000, "currency": "KES", "supplier_norm": "Supplier A"},  # Different ocid
    ]
    
    result = check_quality(candidates)
    
    # Should have 3 in pool (A1, A3, A4)
    assert result["pool_size"] == 3
    assert result["counts"]["excluded"] == 1
    assert result["counts"]["ok"] == 3
    
    # A2 should be excluded as duplicate
    for r in result["results"]:
        if r["award_id"] == "A2":
            assert r["verdict"] == "excluded"
            assert "duplicate_row" in r["reasons"]


def test_median_ignores_excluded():
    """Test the median ignores excluded values (an absurd duplicate does not skew it)."""
    candidates = [
        {"award_id": "A1", "value_kes": 1000000, "currency": "KES"},
        {"award_id": "A2", "value_kes": 2000000, "currency": "KES"},
        {"award_id": "A3", "value_kes": 3000000, "currency": "KES"},
        {"award_id": "A4", "value_kes": 4000000, "currency": "KES"},
        {"award_id": "A5", "value_kes": 5000000, "currency": "KES"},
        {"award_id": "A6", "value_kes": 1000000, "currency": "KES"},  # Duplicate, will be excluded
    ]
    
    result = check_quality(candidates)
    
    # Median should be 3000000 (from A1-A5), not affected by duplicate
    assert result["median_kes"] == 3000000.0
    assert result["pool_size"] == 5


def test_extreme_values_suspect():
    """Test extreme values are suspect, normal values are ok."""
    candidates = [
        {"award_id": "A1", "value_kes": 100000, "currency": "KES"},    # 0.1x median - suspect
        {"award_id": "A2", "value_kes": 500000, "currency": "KES"},    # 0.5x median - ok
        {"award_id": "A3", "value_kes": 1000000, "currency": "KES"},   # Median - ok
        {"award_id": "A4", "value_kes": 2000000, "currency": "KES"},   # 2x median - ok
        {"award_id": "A5", "value_kes": 10000000, "currency": "KES"},  # 10x median - suspect
    ]
    
    result = check_quality(candidates, outlier_multiple=10)
    
    assert result["pool_size"] == 5
    assert result["counts"]["suspect"] == 2
    assert result["counts"]["ok"] == 3
    
    # Check suspect verdicts
    for r in result["results"]:
        if r["award_id"] in ["A1", "A5"]:
            assert r["verdict"] == "suspect"
            assert r["ratio_to_median"] is not None


def test_small_pool_no_suspect():
    """Test a pool smaller than min_comparables gives enough_comparables false and no suspect verdicts."""
    candidates = [
        {"award_id": "A1", "value_kes": 1000000, "currency": "KES"},
        {"award_id": "A2", "value_kes": 2000000, "currency": "KES"},
        {"award_id": "A3", "value_kes": 3000000, "currency": "KES"},
    ]
    
    result = check_quality(candidates, min_comparables=5)
    
    assert result["pool_size"] == 3
    assert result["enough_comparables"] is False
    assert result["counts"]["suspect"] == 0
    assert result["counts"]["ok"] == 3


def test_output_order_matches_input():
    """Test output order matches input order. The input is not mutated."""
    candidates = [
        {"award_id": "A3", "value_kes": 3000000, "currency": "KES"},
        {"award_id": "A1", "value_kes": 1000000, "currency": "KES"},
        {"award_id": "A2", "value_kes": 2000000, "currency": "KES"},
    ]
    
    original_candidates = candidates.copy()
    result = check_quality(candidates)
    
    # Check input is not mutated
    assert candidates == original_candidates
    
    # Check output order matches input order
    assert result["results"][0]["award_id"] == "A3"
    assert result["results"][1]["award_id"] == "A1"
    assert result["results"][2]["award_id"] == "A2"


def test_loader_flags_in_notes():
    """Test loader flags appear in notes and do not change the verdict."""
    candidates = [
        {"award_id": "A1", "value_kes": 1000000, "currency": "KES", "flags": ["no_supplier", "unusual_method"]},
        {"award_id": "A2", "value_kes": 2000000, "currency": "KES", "flags": ["no_category"]},
    ]
    
    result = check_quality(candidates)
    
    assert result["counts"]["ok"] == 2
    assert result["results"][0]["notes"] == ["no_supplier", "unusual_method"]
    assert result["results"][1]["notes"] == ["no_category"]
    assert result["results"][0]["verdict"] == "ok"
    assert result["results"][1]["verdict"] == "ok"


def test_missing_required_fields():
    """Test missing award_id or value_kes is excluded, naming what is missing."""
    # Missing value_kes
    result = check_quality([{"award_id": "A1"}])
    assert result["pool_size"] == 0
    assert result["counts"]["excluded"] == 1
    assert result["results"][0]["verdict"] == "excluded"
    assert result["results"][0]["reasons"] == ["value_not_positive"]

    # Missing award_id
    result = check_quality([{"value_kes": 1000000}])
    assert result["counts"]["excluded"] == 1
    assert result["results"][0]["award_id"] is None
    assert result["results"][0]["reasons"] == ["missing_award_id"]

    # Both missing
    result = check_quality([{}])
    assert result["pool_size"] == 0
    assert result["results"][0]["reasons"] == ["missing_award_id"]


def test_empty_list():
    """Test empty list returns empty result with enough_comparables false."""
    result = check_quality([])
    
    assert result["pool_size"] == 0
    assert result["median_kes"] is None
    assert result["enough_comparables"] is False
    assert result["counts"] == {"ok": 0, "suspect": 0, "excluded": 0}
    assert result["results"] == []


def test_wrapper_uses_settings():
    """Test wrapper function uses settings from config."""
    candidates = [
        {"award_id": "A1", "value_kes": 1000000, "currency": "KES"},
        {"award_id": "A2", "value_kes": 2000000, "currency": "KES"},
        {"award_id": "A3", "value_kes": 3000000, "currency": "KES"},
    ]
    
    # Mock settings for testing
    from unittest.mock import patch
    from mcp_server.tools.flag_data_quality import settings
    
    with patch.object(settings, 'outlier_multiple', 5):
        with patch.object(settings, 'min_comparables', 3):
            result = flag_data_quality(candidates)
            assert result["enough_comparables"] is True