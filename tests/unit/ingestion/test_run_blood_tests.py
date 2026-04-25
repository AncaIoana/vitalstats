"""
Tests for the run() error handling in extract_blood_tests.py.

We don't touch a real DB or Google Sheets API — everything is mocked.
Each test fakes the external dependencies and asserts on what run() does
in response to a specific bad situation.

Run with:
    uv run pytest tests/unit/ingestion/test_run_blood_tests.py -v
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

# ── Shared test data ─────────────────────────────────────────────────────────

# A minimal set of valid rows — all required fields present, known values.
# Used as the baseline "happy path" input.
VALID_ROWS = [
    {
        "Date": "6-Apr-2023",
        "Test Type": "Biochemistry",
        "Analyte": "Haemoglobin",
        "Result": "13.2",
        "Unit": "g/dL",
        "Reference Interval": "11.5-16.5",
        "Collection": "St Mary Mead Clinic",
        "Notes": "",
    },
]

# The module path prefix — all patches must point into this module,
# because that's where the names are *used* (imported into).
_MOD = "ingestion.google_sheets.extract_blood_tests"


# ── Test 1: hard failure when fetch_tab raises ───────────────────────────────

@patch(f"{_MOD}.write_raw_json")          # arg 7 — outermost decorator, last arg
@patch(f"{_MOD}.get_existing_hashes")     # arg 6
@patch(f"{_MOD}.get_previous_row_count")  # arg 5
@patch(f"{_MOD}.finish_run")              # arg 4
@patch(f"{_MOD}.fail_run")                # arg 3
@patch(f"{_MOD}.fetch_tab")               # arg 2
@patch(f"{_MOD}.start_run")               # arg 1
@patch(f"{_MOD}.get_db_connection")       # arg 0 — innermost decorator, first arg
def test_run_aborts_when_fetch_fails(
    mock_get_conn,           # ← get_db_connection
    mock_start_run,          # ← start_run
    mock_fetch_tab,          # ← fetch_tab
    mock_fail_run,           # ← fail_run
    mock_finish_run,         # ← finish_run
    mock_prev_count,         # ← get_previous_row_count
    mock_existing_hashes,    # ← get_existing_hashes
    mock_write_json,         # ← write_raw_json
):
    """
    When fetch_tab raises an exception, run() should:
    - call fail_run exactly once
    - never call finish_run (because we aborted)
    """
    # ── Arrange ──────────────────────────────────────────────────────────────
    # get_db_connection returns a mock connection object.
    # We don't need to configure it further — run() just passes it around.
    mock_get_conn.return_value = MagicMock()

    # start_run returns a fake run_id string.
    # run() uses this to reference the correct log row in later DB calls.
    mock_start_run.return_value = "test-run-id-001"

    # fetch_tab raises — simulates Google Sheets API being unreachable.
    # side_effect means "when called, raise this instead of returning a value".
    mock_fetch_tab.side_effect = Exception("Connection refused")

    # ── Act ──────────────────────────────────────────────────────────────────
    # We must set the env var so run() doesn't sys.exit(1) before even starting
    # patch.dict temporarily adds/overrides entries in os.environ for this test
    with patch("os.environ.get", return_value="fake-sheet-id"):
        from ingestion.google_sheets.extract_blood_tests import run
        run()

    # ── Assert ───────────────────────────────────────────────────────────────
    # Hard failure: fail_run must have been called exactly once.
    mock_fail_run.assert_called_once()

    # The error message passed to fail_run should mention the exception text.
    call_kwargs = mock_fail_run.call_args
    assert "Connection refused" in str(call_kwargs)

    # finish_run must NOT have been called — we aborted before reaching it.
    mock_finish_run.assert_not_called()


# ── Test 2: hard failure when columns are missing ────────────────────────────

@patch(f"{_MOD}.write_raw_json")
@patch(f"{_MOD}.get_existing_hashes")
@patch(f"{_MOD}.get_previous_row_count")
@patch(f"{_MOD}.finish_run")
@patch(f"{_MOD}.fail_run")
@patch(f"{_MOD}.fetch_tab")
@patch(f"{_MOD}.start_run")
@patch(f"{_MOD}.get_db_connection")
def test_run_aborts_on_missing_columns(
    mock_get_conn,
    mock_start_run,
    mock_fetch_tab,
    mock_fail_run,
    mock_finish_run,
    mock_prev_count,
    mock_existing_hashes,
    mock_write_json,
):
    """
    When fetch_tab returns rows that are missing the "Analyte" column, 
    run() should:
    - call fail_run exactly once
    - never call finish_run (because we aborted)
    """
    # ── Arrange ──────────────────────────────────────────────────────────────
    mock_get_conn.return_value = MagicMock()
    mock_start_run.return_value = "test-run-id-002"
    mock_fetch_tab.return_value = [
        {
            "Date": "6-Apr-2023",
            "Test Type": "Biochemistry",
            # "Analyte" column is missing here
            "Result": "13.2",
            "Unit": "g/dL",
            "Reference Interval": "11.5-16.5",
            "Collection": "St Mary Mead Clinic",
            "Notes": "",
        },
    ]

    # ── Act ──────────────────────────────────────────────────────────────────
    with patch("os.environ.get", return_value="fake-sheet-id"):
        from ingestion.google_sheets.extract_blood_tests import run
        run()

    # ── Assert ───────────────────────────────────────────────────────────────
    mock_fail_run.assert_called_once()
    call_kwargs = mock_fail_run.call_args
    assert "Missing expected columns" in str(call_kwargs)

    mock_finish_run.assert_not_called()


# ── Test 3: hard failure when row counts drop ────────────────────────────

@patch(f"{_MOD}.write_raw_json")
@patch(f"{_MOD}.get_existing_hashes")
@patch(f"{_MOD}.get_previous_row_count")
@patch(f"{_MOD}.finish_run")
@patch(f"{_MOD}.fail_run")
@patch(f"{_MOD}.fetch_tab")
@patch(f"{_MOD}.start_run")
@patch(f"{_MOD}.get_db_connection")
def test_run_aborts_on_row_count_drop(
    mock_get_conn,
    mock_start_run,
    mock_fetch_tab,
    mock_fail_run,
    mock_finish_run,
    mock_prev_count,
    mock_existing_hashes,
    mock_write_json,
):
    """
    When fetch_tab returns less rows that the previous count, run() should:
    - call fail_run exactly once
    - never call finish_run (because we aborted)
    """
    # ── Arrange ──────────────────────────────────────────────────────────────
    mock_get_conn.return_value = MagicMock()
    mock_start_run.return_value = "test-run-id-003"
    mock_fetch_tab.return_value = VALID_ROWS
    mock_prev_count.return_value = 999

    # ── Act ──────────────────────────────────────────────────────────────────
    with patch("os.environ.get", return_value="fake-sheet-id"):
        from ingestion.google_sheets.extract_blood_tests import run
        run()

    # ── Assert ───────────────────────────────────────────────────────────────
    mock_fail_run.assert_called_once()
    call_kwargs = mock_fail_run.call_args
    assert "Row count dropped" in str(call_kwargs)

    mock_finish_run.assert_not_called()


# ── Test 4: soft for rows missing test type ──────────────────────────────────

@patch(f"{_MOD}.write_raw_json")
@patch(f"{_MOD}.get_existing_hashes")
@patch(f"{_MOD}.get_previous_row_count")
@patch(f"{_MOD}.finish_run")
@patch(f"{_MOD}.fail_run")
@patch(f"{_MOD}.fetch_tab")
@patch(f"{_MOD}.start_run")
@patch(f"{_MOD}.get_db_connection")
def test_run_skips_row_with_missing_test_type(
    mock_get_conn,
    mock_start_run,
    mock_fetch_tab,
    mock_fail_run,
    mock_finish_run,
    mock_prev_count,
    mock_existing_hashes,
    mock_write_json,
):
    """
    When fetch_tab returns less rows that the previous count, run() should:
    - never call fail_run 
    - call finish_run exactly once
    """
    # ── Arrange ──────────────────────────────────────────────────────────────
    mock_get_conn.return_value = MagicMock()
    mock_start_run.return_value = "test-run-id-004"
    mock_fetch_tab.return_value = [
        {
            "Date": "6-Apr-2023",
            "Test Type": "",
            "Analyte": "Haemoglobin",
            "Result": "13.2",
            "Unit": "g/dL",
            "Reference Interval": "11.5-16.5",
            "Collection": "St Mary Mead Clinic",
            "Notes": "",
        },
    ]
    mock_prev_count.return_value = 0
    mock_existing_hashes.return_value = set()
    mock_write_json.return_value = Path("fake/path.json")

    # ── Act ──────────────────────────────────────────────────────────────────
    with patch("os.environ.get", return_value="fake-sheet-id"):
        from ingestion.google_sheets.extract_blood_tests import run
        run()

    # ── Assert ───────────────────────────────────────────────────────────────
    mock_fail_run.assert_not_called()
    mock_finish_run.assert_called_once()
