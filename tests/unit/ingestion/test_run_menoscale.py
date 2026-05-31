"""
Tests for the run() error handling in extract_menoscale.py.

We don't touch a real DB or Google Sheets API — everything is mocked.
Each test fakes the external dependencies and asserts on what run() does
in response to a specific bad situation.

Run with:
    uv run pytest tests/unit/ingestion/test_run_menoscale.py -v
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

# ── Shared test data ─────────────────────────────────────────────────────────

# A minimal set of valid rows — all required fields present, known values.
# Used as the baseline "happy path" input.
VALID_ROWS = [
    {"Date": "6-Sep-2024", "Score (out of 100)": 14},
]

# The module path prefix — all patches must point into this module,
# because that's where the names are *used* (imported into).
_MOD = "ingestion.google_sheets.extract_menoscale"


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
        from ingestion.google_sheets.extract_menoscale import run
        run()

    # ── Assert ───────────────────────────────────────────────────────────────
    # Hard failure: fail_run must have been called exactly once.
    mock_fail_run.assert_called_once()

    # The error message passed to fail_run should mention the exception text.
    call_kwargs = mock_fail_run.call_args
    assert "Connection refused" in str(call_kwargs)

    # finish_run must NOT have been called — we aborted before reaching it.
    mock_finish_run.assert_not_called()

# ── Test 2: soft failure when date is unparseable ────────────────────────────

@patch(f"{_MOD}.write_raw_json")
@patch(f"{_MOD}.get_existing_hashes")
@patch(f"{_MOD}.get_previous_row_count")
@patch(f"{_MOD}.finish_run")
@patch(f"{_MOD}.fail_run")
@patch(f"{_MOD}.fetch_tab")
@patch(f"{_MOD}.start_run")
@patch(f"{_MOD}.get_db_connection")
def test_run_skips_row_with_unparseable_date(
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
    When fetch_tab returns rows with unparseable date, run() should:
    - never call fail_run exactly
    - call finish_run once
    """
    # ── Arrange ──────────────────────────────────────────────────────────────
    mock_get_conn.return_value = MagicMock()
    mock_start_run.return_value = "test-run-id-002"
    mock_fetch_tab.return_value = [
        {"Date": "2024 september", "Score (out of 100)": 14},
    ]
    mock_prev_count.return_value = 0

    # ── Act ──────────────────────────────────────────────────────────────────
    with patch("os.environ.get", return_value="fake-sheet-id"):
        from ingestion.google_sheets.extract_menoscale import run
        run()

    # ── Assert ───────────────────────────────────────────────────────────────
    mock_fail_run.assert_not_called()
    mock_finish_run.assert_called_once()

# ── Test 3: soft failure when date is invalid ────────────────────────────

@patch(f"{_MOD}.write_raw_json")
@patch(f"{_MOD}.get_existing_hashes")
@patch(f"{_MOD}.get_previous_row_count")
@patch(f"{_MOD}.finish_run")
@patch(f"{_MOD}.fail_run")
@patch(f"{_MOD}.fetch_tab")
@patch(f"{_MOD}.start_run")
@patch(f"{_MOD}.get_db_connection")
def test_run_skips_row_with_invalid_score(
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
    When fetch_tab returns rows with unparseable date, run() should:
    - never call fail_run exactly
    - call finish_run once
    """
    # ── Arrange ──────────────────────────────────────────────────────────────
    mock_get_conn.return_value = MagicMock()
    mock_start_run.return_value = "test-run-id-003"
    mock_fetch_tab.return_value = [
        {"Date": "6-Sep-2024", "Score (out of 100)": "-5"},
    ]
    mock_prev_count.return_value = 0

    # ── Act ──────────────────────────────────────────────────────────────────
    with patch("os.environ.get", return_value="fake-sheet-id"):
        from ingestion.google_sheets.extract_menoscale import run
        run()

    # ── Assert ───────────────────────────────────────────────────────────────
    mock_fail_run.assert_not_called()
    mock_finish_run.assert_called_once()


# ── Test 4: soft failure when date is empty ────────────────────────────

@patch(f"{_MOD}.write_raw_json")
@patch(f"{_MOD}.get_existing_hashes")
@patch(f"{_MOD}.get_previous_row_count")
@patch(f"{_MOD}.finish_run")
@patch(f"{_MOD}.fail_run")
@patch(f"{_MOD}.fetch_tab")
@patch(f"{_MOD}.start_run")
@patch(f"{_MOD}.get_db_connection")
def test_run_skips_row_with_empty_date(
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
    When fetch_tab returns rows with empty date, run() should:
    - never call fail_run exactly
    - call finish_run once
    """
    # ── Arrange ──────────────────────────────────────────────────────────────
    mock_get_conn.return_value = MagicMock()
    mock_start_run.return_value = "test-run-id-004"
    mock_fetch_tab.return_value = [
        {"Date": "", "Score (out of 100)": "25"},
    ]
    mock_prev_count.return_value = 0

    # ── Act ──────────────────────────────────────────────────────────────────
    with patch("os.environ.get", return_value="fake-sheet-id"):
        from ingestion.google_sheets.extract_menoscale import run
        run()

    # ── Assert ───────────────────────────────────────────────────────────────
    mock_fail_run.assert_not_called()
    mock_finish_run.assert_called_once()
