"""
Unit tests for parse_ref_interval() in ingestion/utils/ref_interval_parser.py.
To run: uv run pytest tests/unit/ingestion/test_ref_interval_parser.py -v
"""

from ingestion.utils.ref_interval_parser import ParsedRefInterval, parse_ref_interval


def test_empty_string():
    """'' should produce ref_type='unknown'."""
    parsed_ref = parse_ref_interval("")
    assert parsed_ref == ParsedRefInterval(ref_type="unknown")


def test_not_applicable():
    """'N/A' should produce ref_type='categorical'."""
    parsed_ref = parse_ref_interval("N/A")
    assert parsed_ref == ParsedRefInterval(ref_type="categorical")


def test_simple_range():
    """
    '35-50' should produce 
    ref_type='range', ref_low='35.0, ref_high=50.0"""
    parsed_ref = parse_ref_interval("35-50")
    assert parsed_ref == ParsedRefInterval(ref_type="range",
                                           ref_low=35.0,
                                           ref_high=50.0)


def test_range_with_spaces():
    """
    '2.20 - 2.60' should produce 
    ref_type='range', ref_low=2.20, ref_high=2.60."""
    parsed_ref = parse_ref_interval("2.20 - 2.60")
    assert parsed_ref == ParsedRefInterval(ref_type="range",
                                           ref_low=2.20,
                                           ref_high=2.60)


def test_range_with_glued_unit():
    """
    '15.00-150.00ug/L' should produce 
    ref_type='categorical', ref_low=15.0, ref_high=150.0."""
    parsed_ref = parse_ref_interval("15.00-150.00ug/L")
    assert parsed_ref == ParsedRefInterval(ref_type="range",
                                           ref_low=15.0,
                                           ref_high=150.0)


def test_less_than():
    """'<35' should produce ref_type='lt', ref_high=35.0."""
    parsed_ref = parse_ref_interval("<35")
    assert parsed_ref == ParsedRefInterval(ref_type="lt",
                                           ref_high=35.0)


def test_less_than_with_space():
    """'< 20' should produce ref_type='lt', ref_high=20.0."""
    parsed_ref = parse_ref_interval("< 20")
    assert parsed_ref == ParsedRefInterval(ref_type="lt",
                                           ref_high=20.0)


def test_greater_than():
    """'>1.99%' should produce ref_type='gt', ref_low=1.99."""
    parsed_ref = parse_ref_interval(">1.99%")
    assert parsed_ref == ParsedRefInterval(ref_type="gt",
                                           ref_low=1.99)


def test_known_prefix():
    """
    'Adults: <1.2' should produce 
    ref_type='lt', ref_high=1.2, note=Reference range applies to: adults."""
    parsed_ref = parse_ref_interval("Adults: <1.2")
    assert parsed_ref == ParsedRefInterval(ref_type="lt",
                                           ref_high=1.2,
                                           note="Reference range applies to: adults")


def test_narrative():
    """
    '49-90 for women60-110 for men' should produce 
    ref_type='narrative', note='49-90 for women60-110 for men'.
    """
    parsed_ref = parse_ref_interval("49-90 for women60-110 for men")
    assert parsed_ref == ParsedRefInterval(ref_type="narrative",
                                           note="49-90 for women60-110 for men")
