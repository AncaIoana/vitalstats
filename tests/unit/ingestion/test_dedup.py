"""
Unit tests covering hash_row and get_existing_hashes
Run uv run pytest tests/unit/ingestion/test_dedup.py -v
"""

from unittest.mock import MagicMock
from ingestion.utils.hashing import hash_row
from ingestion.utils.pipeline import get_existing_hashes


def make_mock_conn(rows):
    """
    Helper: returns a mock DB connection whose cursor returns `rows`.
    """
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = rows
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn


def test_hash_row_is_deterministic(single_blood_test_row):
    """Calling hash_row twice with the same row gives the same result."""
    assert hash_row(single_blood_test_row) == hash_row(single_blood_test_row)


def test_hash_row_key_order_independent(single_blood_test_row):
    """Calling hash_row on a row and its reverse gives the same result."""
    inv_single_blood_test_row = dict(reversed(list(single_blood_test_row.items())))
    assert hash_row(single_blood_test_row) == hash_row(inv_single_blood_test_row)


def test_hash_row_returns_64_char_hex(single_blood_test_row):
    """Calling hash_row creates a 64 character hexadecimal string."""
    assert len(hash_row(single_blood_test_row)) == 64
    int(hash_row(single_blood_test_row), 16)  # raises ValueError if not hex
    assert True


def test_hash_row_different_rows_differ(blood_test_rows):
    """Calling hash_row on different rows produces different hashes."""
    assert hash_row(blood_test_rows[0]) != hash_row(blood_test_rows[1])


def test_hash_row_duplicate_rows_match(blood_test_rows):
    """Calling hash_row on a duplicate row gives the same result."""
    assert hash_row(blood_test_rows[0]) == hash_row(blood_test_rows[11])


def test_get_existing_hashes_returns_set():
    """Calling get_existing_hashes on two rows returns a set containing the two hashes"""
    fake_rows = [("abc123",), ("def456",)]
    mock_conn = make_mock_conn(fake_rows)
    result = get_existing_hashes(mock_conn, "raw.blood_tests")
    assert isinstance(result, set)
    assert result == {"abc123", "def456"}


def test_get_existing_hashes_empty_table():
    """Calling get_existing_hashes on an empty table returns an empty set."""
    fake_rows = []
    mock_conn = make_mock_conn(fake_rows)
    result = get_existing_hashes(mock_conn, "raw.blood_tests")
    assert isinstance(result, set)
    assert result == set()
