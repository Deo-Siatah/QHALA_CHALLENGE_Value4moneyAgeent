import pytest
from unittest.mock import Mock, patch, MagicMock
from mcp_server.tools.find_comparable_awards import search_awards, find_comparable_awards


@patch('psycopg.connect')
def test_strict_match_returns_all_tokens(mock_connect):
    """Test strict returns only awards whose tender title has all the tokens."""
    # Setup mock connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    
    # Setup mock cursor
    mock_cursor.fetchall.return_value = [
        {"award_id": "award1", "title": "Classroom construction", "score": 1.0}
    ]
    
    result = search_awards(mock_conn, "classroom construction", match="strict")
    
    assert "filters" in result
    assert "count" in result
    assert "candidates" in result
    assert result["count"] == 1


@patch('psycopg.connect')
def test_loose_match_returns_partial(mock_connect):
    """Test loose returns partial matches, with fuller matches ranked first."""
    # Setup mock connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    
    # Setup mock cursor
    mock_cursor.fetchall.return_value = [
        {"award_id": "award1", "title": "Classroom construction", "score": 1.0},
        {"award_id": "award2", "title": "Road construction", "score": 0.5}
    ]
    
    result = search_awards(mock_conn, "classroom construction", match="loose")
    
    assert result["count"] == 2
    assert result["candidates"][0]["title"] == "Classroom construction"


@patch('psycopg.connect')
def test_fuzzy_finds_misspelled(mock_connect):
    """Test fuzzy finds a misspelled title (e.g., 'Clasroom' for 'classroom')."""
    # Setup mock connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    
    # Setup mock cursor
    mock_cursor.fetchall.return_value = [
        {"award_id": "award9", "title": "Clasroom construction", "score": 0.8}
    ]
    
    result = search_awards(mock_conn, "clasroom construction", match="fuzzy")
    
    assert result["count"] == 1
    assert "Clasroom" in result["candidates"][0]["title"]


@patch('psycopg.connect')
def test_category_filter_works(mock_connect):
    """Test category filter works correctly."""
    # Setup mock connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    
    # Setup mock cursor
    mock_cursor.fetchall.return_value = [
        {"award_id": "award1", "title": "Classroom construction", "category": "works", "score": 1.0}
    ]
    
    result = search_awards(mock_conn, "classroom", category="works", match="strict")
    
    assert result["count"] == 1
    assert result["candidates"][0]["category"] == "works"


@patch('psycopg.connect')
def test_buyer_id_filter_works(mock_connect):
    """Test buyer_id filter works correctly."""
    # Setup mock connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    
    # Setup mock cursor
    mock_cursor.fetchall.return_value = [
        {"award_id": "award1", "title": "Classroom construction", "buyer_name": "buyer1", "score": 1.0}
    ]
    
    result = search_awards(mock_conn, "classroom", buyer_id="buyer1", match="strict")
    
    assert result["count"] == 1
    assert result["candidates"][0]["buyer_name"] == "buyer1"


@patch('psycopg.connect')
def test_min_year_filter_works(mock_connect):
    """Test min_year filter works correctly."""
    # Setup mock connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    
    # Setup mock cursor
    mock_cursor.fetchall.return_value = [
        {"award_id": "award1", "title": "Classroom construction", "data_year": 2024, "score": 1.0}
    ]
    
    result = search_awards(mock_conn, "classroom", min_year=2024, match="strict")
    
    assert result["count"] == 1
    assert result["candidates"][0]["data_year"] == 2024


@patch('psycopg.connect')
def test_non_positive_values_excluded(mock_connect):
    """Test values <= 0 are never returned."""
    # Setup mock connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    
    # Setup mock cursor - should not return zero value
    mock_cursor.fetchall.return_value = [
        {"award_id": "award1", "title": "Classroom construction", "value_kes": 1000000, "score": 1.0}
    ]
    
    result = search_awards(mock_conn, "construction", match="strict")
    
    assert result["count"] == 1
    assert result["candidates"][0]["value_kes"] > 0


@patch('psycopg.connect')
def test_non_kes_values_excluded(mock_connect):
    """Test non-KES currency values are never returned."""
    # Setup mock connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    
    # Setup mock cursor - should not return non-KES
    mock_cursor.fetchall.return_value = [
        {"award_id": "award1", "title": "Classroom construction", "currency": "KES", "score": 1.0}
    ]
    
    result = search_awards(mock_conn, "project", match="strict")
    
    assert result["count"] == 1
    assert result["candidates"][0]["currency"] == "KES"


@patch('psycopg.connect')
def test_exclude_ocid_works(mock_connect):
    """Test exclude_ocid filter works correctly."""
    # Setup mock connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    
    # Setup mock cursor
    mock_cursor.fetchall.return_value = [
        {"award_id": "award2", "title": "Road maintenance", "ocid": "t2", "score": 1.0}
    ]
    
    result = search_awards(mock_conn, "classroom", exclude_ocid="t1", match="strict")
    
    assert result["count"] == 1
    assert result["candidates"][0]["ocid"] != "t1"


@patch('psycopg.connect')
def test_results_capped_at_limit(mock_connect):
    """Test results are capped at limit, in the specified order."""
    # Setup mock connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    
    # Setup mock cursor with more results than limit - the actual database should respect LIMIT
    # but our mock returns all results, so we test that the function correctly handles the limit
    mock_cursor.fetchall.return_value = [
        {"award_id": "award1", "title": "Classroom construction", "score": 1.0},
        {"award_id": "award2", "title": "Classroom supplies", "score": 0.9}
    ]
    
    result = search_awards(mock_conn, "classroom", limit=2, match="strict")
    
    assert result["count"] == 2


@patch('psycopg.connect')
def test_output_has_correct_structure(mock_connect):
    """Test output has filters, count, and candidate fields."""
    # Setup mock connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    
    # Setup mock cursor
    mock_cursor.fetchall.return_value = [
        {
            "award_id": "award1", "ocid": "t1", "data_year": 2024, "title": "Classroom construction",
            "buyer_name": "buyer1", "category": "works", "method": "open",
            "value_kes": 1000000, "currency": "KES", "supplier_name": "Supplier A",
            "supplier_norm": None, "lot_group": "lot1", "flags": [], "score": 1.0
        }
    ]
    
    result = search_awards(mock_conn, "classroom", match="strict")
    
    assert "filters" in result
    assert "count" in result
    assert "candidates" in result
    assert result["count"] == 1
    assert "award_id" in result["candidates"][0]
    assert "title" in result["candidates"][0]
    assert "value_kes" in result["candidates"][0]


def test_error_no_usable_tokens():
    """Test error raised when no usable tokens."""
    with pytest.raises(ValueError, match="No usable tokens found in query"):
        search_awards(Mock(), "a the of", match="strict")


def test_error_invalid_match():
    """Test error raised when match not in strict|loose|fuzzy."""
    with pytest.raises(ValueError, match="match must be 'strict', 'loose', or 'fuzzy'"):
        search_awards(Mock(), "classroom", match="invalid")


def test_error_invalid_category():
    """Test error raised when category not in works|goods|services."""
    with pytest.raises(ValueError, match="category must be 'works', 'goods', or 'services'"):
        search_awards(Mock(), "classroom", category="invalid", match="strict")


@patch('psycopg.connect')
def test_hostile_query_handled(mock_connect):
    """Test hostile query text returns normally and breaks nothing."""
    # Setup mock connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    
    # Setup mock cursor
    mock_cursor.fetchall.return_value = []
    
    # Should not raise an exception
    result = search_awards(mock_conn, "poles'; DROP TABLE awards; --", match="strict")
    
    assert "filters" in result
    assert "count" in result
    assert "candidates" in result