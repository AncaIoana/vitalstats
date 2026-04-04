"""
Unit tests for hash_row in utils/hashing.py.
"""

from ingestion.utils.hashing import hash_row


def test_hash_row_returns_string(single_blood_test_row):
    """hash_row should return a non-empty string."""
    result = hash_row(single_blood_test_row)
    assert isinstance(result, str)
    assert len(result) > 0


def test_hash_row_identical_rows_produce_same_hash(single_blood_test_row):
    """
    Two identical dicts must produce the same hash — this is the whole
    point of hash-based deduplication.
    """
    hash1 = hash_row(single_blood_test_row)
    hash2 = hash_row(dict(single_blood_test_row))  # copy, same content
    assert hash1 == hash2


def test_hash_row_different_rows_produce_different_hashes(blood_test_rows):
    """
    Different rows must produce different hashes.
    We use the first two rows from the fixture — they have different analytes.
    """
    hash1 = hash_row(blood_test_rows[0])
    hash2 = hash_row(blood_test_rows[1])
    assert hash1 != hash2


def test_hash_row_one_field_change_changes_hash(single_blood_test_row):
    """
    Changing a single field must change the hash — this is what lets us
    detect edits to past rows (ADR-005).
    """
    original_hash = hash_row(single_blood_test_row)
    modified = {**single_blood_test_row, "Result": "999"}
    modified_hash = hash_row(modified)
    assert original_hash != modified_hash
