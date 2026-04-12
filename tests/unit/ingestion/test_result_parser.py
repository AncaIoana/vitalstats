"""
Unit tests for parse_result() in ingestion/utils/result_parser.py.
To run: uv run pytest tests/unit/ingestion/test_result_parser.py -v
"""

from ingestion.utils.result_parser import ParsedResult, parse_result


def test_less_than_qualifier():
    """'< 0.6' should produce is_numeric=True, numeric=0.6, qualifier='lt'."""
    parsed = parse_result("< 0.6")
    assert parsed == ParsedResult(is_numeric=True, numeric=0.6, qualifier="lt")


def test_greater_than_qualifier():
    """'>20' should produce is_numeric=True, numeric=20.0, qualifier='gt'."""
    parsed = parse_result(">20")
    assert parsed == ParsedResult(is_numeric=True, numeric=20.0, qualifier="gt")


def test_plain_numeric():
    """'3.14' should produce is_numeric=True, numeric=3.14."""
    parsed = parse_result("3.14")
    assert parsed == ParsedResult(is_numeric=True, numeric=3.14)


def test_categorical_text():
    """'Positive' should be normalised to is_numeric=False, text='positive'."""
    parsed = parse_result("Positive")
    assert parsed == ParsedResult(is_numeric=False, text="positive")


def test_free_text():
    """'Hercule Poirot' should be normalised to is_numeric=False, text='hercule_poirot'."""
    parsed = parse_result("Hercule Poirot")
    assert parsed == ParsedResult(is_numeric=False, text="hercule_poirot")
