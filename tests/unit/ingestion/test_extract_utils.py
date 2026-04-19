"""
Unit tests for shared ingestion utilities in extract_utils.py.
"""

from ingestion.utils.pipeline import validate_columns


def test_validate_columns_all_present():
    """All expected columns are present — should return empty list."""
    rows = [{"Date": "6-Apr-2023", "Test Type": "Biochemistry", "Analyte": "ALT"}]
    missing = validate_columns(rows, expected_columns=["Date", "Test Type", "Analyte"])
    assert missing == []


def test_validate_columns_one_missing():
    """One expected column absent — should return its name."""
    rows = [{"Date": "6-Apr-2023", "Test Type": "Biochemistry"}]
    missing = validate_columns(rows, expected_columns=["Date", "Test Type", "Analyte"])
    assert missing == ["Analyte"]


def test_validate_columns_multiple_missing():
    """Multiple missing columns — should return all of them, sorted."""
    rows = [{"Date": "6-Apr-2023"}]
    missing = validate_columns(rows, expected_columns=["Date", "Test Type", "Analyte"])
    assert missing == ["Analyte", "Test Type"]   # sorted alphabetically


def test_validate_columns_empty_rows():
    """Empty row list — nothing to validate, should return empty list."""
    assert validate_columns([], expected_columns=["Date", "Test Type"]) == []
