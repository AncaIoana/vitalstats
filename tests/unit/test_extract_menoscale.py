import pytest
from datetime import date
from ingestion.google_sheets.extract_menoscale import _parse_menoscale_date, _validate_score

# test _parse_menoscale_date ──────────────────────────────────────────
def test_parse_hyphen_format():
    assert _parse_menoscale_date("6-Sep-2024") == date(2024, 9, 6)


def test_parse_space_format():
    assert _parse_menoscale_date("16 Apr 2025") == date(2025, 4, 16)


def test_parse_strips_whitespace():
    assert _parse_menoscale_date("  6-Sep-2024  ") == date(2024, 9, 6)


def test_parse_invalid_raises():
    with pytest.raises(ValueError):
        _parse_menoscale_date("not-a-date")

# test _validate_score ────────────────────────────────────────────────────
def test_validate_score_valid():
    assert _validate_score("14") == 14


def test_validate_score_boundary_zero():
    assert _validate_score("0") == 0


def test_validate_score_boundary_hundred():
    assert _validate_score("100") == 100


def test_validate_score_over_limit():
    assert _validate_score("101") is None


def test_validate_score_negative():
    assert _validate_score("-1") is None


def test_validate_score_non_numeric():
    assert _validate_score("alibi") is None


def test_validate_score_strips_whitespace():
    assert _validate_score("  42  ") == 42


def test_validate_score_empty_string():
    assert _validate_score("") is None
