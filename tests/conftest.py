"""
Top-level pytest fixtures available to all tests in the project.
Fixtures return synthetic data from tests/fixtures/sample_data.py —
no real health data is ever used in tests.
"""

import pytest

from fixtures.sample_data import (
    BLOOD_TEST_ROWS,
    MEDICATION_ROWS,
    MENOSCALE_ROWS,
    POIROT_VACCINE_ROWS,
    SINGLE_BLOOD_TEST_ROW,
    VACCINE_ROWS,
)


# ---------------------------------------------------------------------------
# Blood test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def blood_test_rows():
    """
    All synthetic blood test rows, including edge cases:
    - numeric, <value, >value, negative, Not Detected, free text results
    - NHS and private lab (mg/dL) collection sites
    - unknown collection site and unknown analyte rows
    - one exact duplicate row (for deduplication tests)
    """
    return BLOOD_TEST_ROWS


@pytest.fixture
def single_blood_test_row():
    """A single clean blood test row — for tests that only need one record."""
    return SINGLE_BLOOD_TEST_ROW


@pytest.fixture
def blood_test_rows_no_duplicates():
    """Blood test rows with the duplicate removed — 13 unique rows."""
    seen = set()
    unique = []
    for row in BLOOD_TEST_ROWS:
        key = tuple(sorted(row.items()))
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


# ---------------------------------------------------------------------------
# Menoscale fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def menoscale_rows():
    """
    Menoscale rows covering both date formats used in the source tab:
    - "6-Sep-2024"    hyphen-separated
    - "16 Apr 2025"   space-separated
    - "1 January 2026" full month name variant
    """
    return MENOSCALE_ROWS


# ---------------------------------------------------------------------------
# Medication fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def medication_rows():
    """
    All synthetic medication rows, including edge cases:
    - ongoing medication (end_date = None)
    - ended medication
    - frequency = 0 (paused/stopped)
    - frequency = 0.5 (alternate days)
    - clinically significant medication (Metyrapone)
    """
    return MEDICATION_ROWS


@pytest.fixture
def active_medication_rows():
    """Only rows where frequency > 0 and end_date is None (currently active)."""
    return [
        r for r in MEDICATION_ROWS
        if r["Frequency (times/day)"] and float(r["Frequency (times/day)"]) > 0
        and r["End Date"] is None
    ]


# ---------------------------------------------------------------------------
# Vaccine fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def vaccine_rows():
    """
    All synthetic vaccine rows, including Hastings rows.
    Use this to test that the Poirot-only filter works correctly.
    """
    return VACCINE_ROWS


@pytest.fixture
def poirot_vaccine_rows():
    """
    Only Poirot's vaccine rows — the expected output after the name filter
    is applied. Use this to assert correct filter behaviour.
    """
    return POIROT_VACCINE_ROWS
