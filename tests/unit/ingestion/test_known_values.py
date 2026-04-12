"""
Unit tests for the known values registry (ingestion/config/known_values.py).

These tests exist because the ingestion pipeline makes hard/soft failure
decisions based on these lists. If a value disappears from the registry,
the pipeline breaks in production — these tests catch that in CI.
"""

from ingestion.config.known_values import (
    KNOWN_TEST_TYPES,
    KNOWN_COLLECTION_SITES,
    EXPECTED_COLUMNS_BLOOD_TESTS,
    EXPECTED_COLUMNS_MENOSCALE,
)


# ── Test types ────────────────────────────────────────────────────────────────

def test_known_test_types_contains_core_categories():
    """The six core test type categories must always be present."""
    for expected in [
        "Biochemistry", "Hematology", "Immunochemistry",
        "Microbiology", "Endocrinology", "Coagulation",
    ]:
        assert expected in KNOWN_TEST_TYPES, f"Missing test type: {expected}"


def test_known_test_types_is_not_empty():
    assert len(KNOWN_TEST_TYPES) > 0


# ── Collection sites ──────────────────────────────────────────────────────────

def test_known_collection_sites_contains_nhs_sites():
    """Core NHS collection sites must always be registered."""
    for expected in [
        "New Islington Medical Practice",
        "Salford Royal",
        "Nuffield Health",
        "Pall Mall",
    ]:
        assert expected in KNOWN_COLLECTION_SITES, f"Missing site: {expected}"


def test_known_collection_sites_contains_synevo():
    """Synevo (Romanian private lab, mg/dL units) must be registered."""
    assert "Synevo" in KNOWN_COLLECTION_SITES


def test_known_collection_sites_is_not_empty():
    assert len(KNOWN_COLLECTION_SITES) > 0


# ── Expected columns ──────────────────────────────────────────────────────────

def test_blood_test_expected_columns_complete():
    """All eight source columns must be listed."""
    for col in ["Date", "Test Type", "Analyte", "Result",
                "Unit", "Reference Interval", "Collection", "Notes"]:
        assert col in EXPECTED_COLUMNS_BLOOD_TESTS, f"Missing column: {col}"


def test_menoscale_expected_columns_complete():
    for col in ["Date", "Score (out of 100)"]:
        assert col in EXPECTED_COLUMNS_MENOSCALE, f"Missing column: {col}"
