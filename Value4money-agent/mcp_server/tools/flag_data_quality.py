# A deterministic rules check over candidates from tool 2. No database, no model.
# It decides which candidates are unusable, which look suspicious, and whether the pool is big enough.
# The model later judges only the suspect ones ("typo or a real large contract?") using the title.

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, ValidationError
from config import settings


class Candidate(BaseModel):
    award_id: Optional[str] = None
    value_kes: Optional[float] = None
    # Other fields are allowed but not validated
    model_config = {'extra': 'allow'}


def check_quality(candidates: List[Dict[str, Any]], outlier_multiple: int = 10, min_comparables: int = 5) -> dict:
    """Core quality check function with deterministic rules."""
    # Input validation
    if not candidates:
        return {
            "pool_size": 0,
            "median_kes": None,
            "enough_comparables": False,
            "counts": {"ok": 0, "suspect": 0, "excluded": 0},
            "results": []
        }
    
    # Validate each candidate has required fields, results list matches input order
    results = [None] * len(candidates)
    validated_candidates = []
    for i, candidate in enumerate(candidates):
        try:
            validated = Candidate(**candidate)
            validated_candidates.append((i, validated, candidate))
        except ValidationError:
            # Create a result for invalid candidate and exclude it
            results[i] = {
                "award_id": candidate.get("award_id"),
                "verdict": "excluded",
                "reasons": ["invalid_fields"],
                "ratio_to_median": None,
                "notes": candidate.get("flags", [])
            }
            continue
    
    # Apply rules in order
    pool_values = []
    
    for original_idx, validated, original_candidate in validated_candidates:
        result = {
            "award_id": original_candidate.get("award_id"),
            "verdict": "ok",
            "reasons": [],
            "ratio_to_median": None,
            "notes": original_candidate.get("flags", [])
        }
        
        # Rule 1: award_id missing, the row cannot be cited
        if validated.award_id is None:
            result["verdict"] = "excluded"
            result["reasons"].append("missing_award_id")
            results[original_idx] = result
            continue
        
        # Rule 2: value_kes missing or <= 0
        if validated.value_kes is None or validated.value_kes <= 0:
            result["verdict"] = "excluded"
            result["reasons"].append("value_not_positive")
            results[original_idx] = result
            continue
        
        # Rule 3: currency present and not KES
        if original_candidate.get("currency") and original_candidate.get("currency") != "KES":
            result["verdict"] = "excluded"
            result["reasons"].append("non_kes")
            results[original_idx] = result
            continue
        
        # Rule 3: Duplicate row - same ocid, value and supplier
        is_duplicate = False
        for existing_idx, _, existing_candidate in pool_values:
            if (existing_candidate.get("ocid") == original_candidate.get("ocid") and
                existing_candidate["value_kes"] == validated.value_kes and
                existing_candidate.get("supplier_norm") == original_candidate.get("supplier_norm")):
                
                # Keep the one with smaller award_id, exclude this one
                if existing_candidate.get("award_id", "") < result["award_id"]:
                    result["verdict"] = "excluded"
                    result["reasons"].append("duplicate_row")
                    is_duplicate = True
                    break
        
        if is_duplicate:
            results[original_idx] = result
            continue
        
        # Add to pool for median calculation
        pool_values.append((original_idx, validated, original_candidate))
        results[original_idx] = result
    
    # Calculate median
    pool_values.sort(key=lambda x: x[1].value_kes)
    pool_size = len(pool_values)
    
    if pool_size == 0:
        median_kes = None
    elif pool_size % 2 == 1:
        median_kes = pool_values[pool_size // 2][1].value_kes
    else:
        median_kes = (pool_values[pool_size // 2 - 1][1].value_kes + pool_values[pool_size // 2][1].value_kes) / 2
    
    # Rule 5: enough comparables to judge the pool
    enough_comparables = pool_size >= min_comparables
    
    # Rule 6: outliers at or beyond the multiple, inclusive so exactly N times counts
    if enough_comparables and median_kes is not None:
        for original_idx, validated, original_candidate in pool_values:
            ratio = validated.value_kes / median_kes
            
            # Update result with ratio
            result = results[original_idx]
            result["ratio_to_median"] = round(ratio, 2)
            
            # Check for extreme values
            if ratio >= outlier_multiple:
                result["verdict"] = "suspect"
                result["reasons"].append("extreme_high")
            elif ratio <= 1 / outlier_multiple:
                result["verdict"] = "suspect"
                result["reasons"].append("extreme_low")
    
    # Count verdicts
    counts = {"ok": 0, "suspect": 0, "excluded": 0}
    for result in results:
        counts[result["verdict"]] += 1
    
    return {
        "pool_size": pool_size,
        "median_kes": median_kes,
        "enough_comparables": enough_comparables,
        "counts": counts,
        "results": results
    }


def flag_data_quality(candidates: List[Dict[str, Any]]) -> dict:
    """Wrapper MCP tool for flagging data quality."""
    return check_quality(
        candidates,
        outlier_multiple=settings.outlier_multiple,
        min_comparables=settings.min_comparables
    )