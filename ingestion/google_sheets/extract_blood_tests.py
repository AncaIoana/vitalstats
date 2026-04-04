"""
Blood tests ingestion script — blood_tests_bulk tab.

Reads from Google Sheets, validates, deduplicates, writes raw JSON to disk,
loads into raw.blood_tests_raw, and updates pipeline state.

Run with:
    uv run python -m ingestion.google_sheets.extract_blood_tests
"""

import json
import logging
import os
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

from ingestion.config.known_values import (
    EXPECTED_COLUMNS,
    KNOWN_COLLECTION_SITES,
    KNOWN_TEST_TYPES,
)
from ingestion.google_sheets.sheets_client import fetch_tab
from ingestion.utils.hashing import hash_row

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

SOURCE = "blood_tests_bulk"           # identifies this pipeline in the DB
RAW_DIR = Path("data/raw/blood_tests") # local archive directory


# ── Database helpers ──────────────────────────────────────────────────────────

def _get_db_connection():
    """
    Open a psycopg2 connection using DATABASE_URL from the environment.

    Raises:
        EnvironmentError: if DATABASE_URL is not set.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise EnvironmentError("DATABASE_URL environment variable is not set.")
    return psycopg2.connect(url)


def _start_run(conn) -> str:
    """
    Record that a new run has started.

    Inserts a row into pipeline_run_log with status 'running', and upserts
    pipeline_state to 'running'. Returns the run_id so later steps can
    reference it when updating the log.
    """
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw.pipeline_run_log (run_id, source, started_at, status)
            VALUES (%s, %s, %s, 'running')
            """,
            (run_id, SOURCE, started_at),
        )
        cur.execute(
            """
            INSERT INTO raw.pipeline_state (source, last_run_at, status)
            VALUES (%s, %s, 'running')
            ON CONFLICT (source) DO UPDATE
                SET last_run_at = EXCLUDED.last_run_at,
                    status = 'running'
            """,
            (SOURCE, started_at),
        )
    conn.commit()
    return run_id


def _finish_run(
    conn,
    run_id: str,
    *,
    status: str,
    rows_fetched: int = 0,
    rows_ingested: int = 0,
    rows_skipped: int = 0,
    rows_failed: int = 0,
    skipped_detail: list | None = None,
    error_message: str | None = None,
    error_traceback: str | None = None,
) -> None:
    """
    Write the final outcome of this run to pipeline_run_log and pipeline_state.

    Args:
        status: "success" | "partial" | "failed"
        skipped_detail: list of dicts describing rows that were flagged,
                        stored as JSONB in the DB.
    """
    finished_at = datetime.now(timezone.utc)
    detail_json = json.dumps(skipped_detail) if skipped_detail else None

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE raw.pipeline_run_log SET
                finished_at        = %s,
                rows_fetched       = %s,
                rows_ingested      = %s,
                rows_skipped       = %s,
                rows_failed        = %s,
                rows_skipped_detail = %s,
                status             = %s,
                error_message      = %s,
                error_traceback    = %s
            WHERE run_id = %s
            """,
            (
                finished_at, rows_fetched, rows_ingested,
                rows_skipped, rows_failed, detail_json,
                status, error_message, error_traceback,
                run_id,
            ),
        )
        cur.execute(
            """
            UPDATE raw.pipeline_state SET
                status        = %s,
                error_message = %s,
                row_count     = %s
            WHERE source = %s
            """,
            (status, error_message, rows_ingested, SOURCE),
        )
    conn.commit()


def _fail_run(conn, run_id: str, message: str, traceback: str | None = None) -> None:
    """
    Convenience wrapper for hard failures. Calls _finish_run with status='failed'.
    Defined separately so call sites read clearly: _fail_run(...) rather than
    _finish_run(..., status='failed') repeated everywhere.
    """
    _finish_run(
        conn,
        run_id,
        status="failed",
        error_message=message,
        error_traceback=traceback,
    )


# ── Validation helpers ────────────────────────────────────────────────────────

def _validate_columns(rows: list[dict]) -> list[str]:
    """
    Check that all expected columns are present.

    Returns a list of missing column names — empty if all present.
    We only need to check the first row because every row in the response
    has the same keys (padded by sheets_client).
    """
    if not rows:
        return []
    actual = set(rows[0].keys())
    expected = set(EXPECTED_COLUMNS)
    return sorted(expected - actual)


def _get_previous_row_count(conn) -> int:
    """
    Return the row count from the last run stored in pipeline_state.
    Returns 0 if this is the first ever run (no row in pipeline_state yet).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT row_count FROM raw.pipeline_state WHERE source = %s",
            (SOURCE,),
        )
        result = cur.fetchone()
    # fetchone() returns a tuple e.g. (524,) or None if no row found.
    return result[0] if result and result[0] is not None else 0


def _get_existing_hashes(conn) -> set[str]:
    """
    Fetch every row hash already in raw.blood_tests_raw.

    We load these into a Python set so that checking whether a hash
    already exists is O(1) — a set lookup is instant regardless of how
    many hashes are stored.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT row_hash FROM raw.blood_tests_raw")
        return {row[0] for row in cur.fetchall()}


# ── Side-effect helpers ───────────────────────────────────────────────────────

def _log_unknown_value(
    conn,
    run_id: str,
    field: str,
    raw_value: str,
    example_row: dict,
    risk_level: str,
) -> None:
    """
    Write an unrecognised value to silver.stg_unknown_values for manual review.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO silver.stg_unknown_values
                (run_id, source, field, raw_value, example_row, risk_level)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                run_id,
                SOURCE,
                field,
                raw_value,
                json.dumps(example_row, default=str),
                risk_level,
            ),
        )


def _write_raw_json(rows: list[dict], today: date) -> Path:
    """
    Archive the raw rows as JSON, organised by date.

    Path: data/raw/blood_tests/YYYY-MM-DD/blood_tests_bulk.json

    mkdir(parents=True, exist_ok=True) creates the full directory path
    if it doesn't already exist. parents=True means it also creates any
    intermediate directories. exist_ok=True means it won't error if the
    directory is already there.

    Returns the path written to.
    """
    out_dir = RAW_DIR / today.isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "blood_tests_bulk.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2, default=str)
    return out_path


# ── Main orchestrator ─────────────────────────────────────────────────────────

def run() -> None:
    """
    Full ingestion flow for blood_tests_bulk:

        1. Fetch rows from Google Sheets
        2a. Validate columns present (hard failure → abort)
        2b. Validate row count not dropped (hard failure → abort)
        3. Hash rows, detect unknowns, split new vs duplicate
        4. Write raw JSON archive to disk
        5. Insert new rows into raw.blood_tests_raw (single transaction)
        6. Finalise pipeline_run_log and pipeline_state
    """
    load_dotenv()

    sheet_id = os.environ.get("BLOOD_TESTS_SHEET_ID")
    if not sheet_id:
        log.error("BLOOD_TESTS_SHEET_ID environment variable is not set.")
        sys.exit(1)
    # sys.exit(1) terminates the process immediately with exit code 1.
    # We use it here before the DB connection exists, so there's nothing
    # to clean up. Once we have a DB connection, we use _fail_run instead.

    conn = _get_db_connection()
    run_id = _start_run(conn)
    log.info("Run started. run_id=%s source=%s", run_id, SOURCE)

    skipped_detail: list[dict] = []  # accumulates warnings for pipeline_run_log
    has_unknown_site = False          # flips to True if any unknown site appears

    try:
        # ── 1. Fetch ──────────────────────────────────────────────────────────
        log.info("Fetching '%s' from sheet %s", SOURCE, sheet_id)
        try:
            rows = fetch_tab(sheet_id, "blood_tests_bulk")
        except Exception as e:
            import traceback as tb
            msg = f"Failed to fetch from Google Sheets: {e}"
            log.error(msg)
            _fail_run(conn, run_id, msg, tb.format_exc())
            return

        log.info("Fetched %d non-empty rows", len(rows))

        # ── 2a. Validate columns ──────────────────────────────────────────────
        missing = _validate_columns(rows)
        if missing:
            msg = f"Missing expected columns: {missing}. Aborting."
            log.error(msg)
            _fail_run(conn, run_id, msg)
            return

        # ── 2b. Validate row count ────────────────────────────────────────────
        previous_count = _get_previous_row_count(conn)
        if len(rows) < previous_count:
            msg = (
                f"Row count dropped: expected >= {previous_count}, "
                f"got {len(rows)}. Rows may have been deleted from source."
            )
            log.error(msg)
            _fail_run(conn, run_id, msg)
            return

        # ── 3. Hash rows, detect unknowns, split new vs duplicate ─────────────
        existing_hashes = _get_existing_hashes(conn)
        new_rows: list[dict] = []

        for row in rows:
            row_hash = hash_row(row)

            # Missing test type → soft failure, skip row
            test_type = row.get("Test Type")
            if not test_type or not test_type.strip():
                skipped_detail.append({
                    "type": "missing_field",
                    "field": "Test Type",
                    "row": {k: str(v) for k, v in row.items()},
                })
                log.warning("Skipping row with missing Test Type: %s", row.get("Analyte"))
                continue

            test_type = test_type.strip()

            # Unknown test type → hard failure, abort
            if test_type not in KNOWN_TEST_TYPES:
                msg = f"Unknown test type: '{test_type}'. Aborting."
                log.error(msg)
                _fail_run(conn, run_id, msg)
                return

            # Missing collection → soft failure, skip row
            collection = row.get("Collection")
            if not collection or not collection.strip():
                skipped_detail.append({
                    "type": "missing_field",
                    "field": "Collection",
                    "row": {k: str(v) for k, v in row.items()},
                })
                log.warning("Skipping row with missing Collection: %s", row.get("Analyte"))
                continue

            collection = collection.strip()

            # Unknown collection site → warn, continue, mark run partial
            if collection not in KNOWN_COLLECTION_SITES:
                log.warning("Unknown collection site: '%s'", collection)
                _log_unknown_value(
                    conn,
                    run_id,
                    field="Collection",
                    raw_value=collection,
                    example_row=row,
                    risk_level="high",
                )
                skipped_detail.append({
                    "type": "unknown_collection_site",
                    "value": collection,
                    "row": {k: str(v) for k, v in row.items()},
                })
                has_unknown_site = True
                conn.commit()  # commit the stg_unknown_values insert now

            # Skip rows already in the DB (hash-based dedup)
            if row_hash in existing_hashes:
                continue

            new_rows.append({**row, "_hash": row_hash})

        duplicates = len(rows) - len(new_rows)
        log.info("%d new rows to insert, %d duplicates skipped", len(new_rows), duplicates)

        # ── 4. Write raw JSON archive ─────────────────────────────────────────
        today = date.today()
        out_path = _write_raw_json(rows, today)
        log.info("Raw JSON written to %s", out_path)

        # ── 5. Insert new rows into DB (single transaction) ───────────────────
        # All inserts happen inside one transaction. If any insert fails,
        # the entire batch is rolled back — no partial loads.
        with conn.cursor() as cur:
            for row in new_rows:
                row_hash = row.pop("_hash")
                cur.execute(
                    """
                    INSERT INTO raw.blood_tests_raw (
                        source_file, row_hash,
                        date_raw, test_type_raw, analyte_raw,
                        result_raw, unit_raw, reference_interval_raw,
                        collection_raw, notes_raw
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(out_path),
                        row_hash,
                        row.get("Date"),
                        row.get("Test Type"),
                        row.get("Analyte"),
                        row.get("Result"),
                        row.get("Unit"),
                        row.get("Reference Interval"),
                        row.get("Collection"),
                        row.get("Notes"),
                    ),
                )
        conn.commit()
        log.info("Inserted %d rows into raw.blood_tests_raw", len(new_rows))

        # ── 6. Finalise pipeline state ────────────────────────────────────────
        final_status = "partial" if has_unknown_site else "success"
        _finish_run(
            conn,
            run_id,
            status=final_status,
            rows_fetched=len(rows),
            rows_ingested=len(new_rows),
            rows_skipped=duplicates,
            rows_failed=0,
            skipped_detail=skipped_detail or None,
        )
        log.info("Run complete. status=%s", final_status)

    except Exception as e:
        # Catch-all for any unexpected error not handled above.
        # Roll back any uncommitted DB writes before logging the failure.
        import traceback as tb
        msg = f"Unexpected error: {e}"
        log.exception(msg)
        try:
            conn.rollback()
            _fail_run(conn, run_id, msg, tb.format_exc())
        except Exception:
            pass  # if the DB itself is broken, nothing we can do

    finally:
        conn.close()


if __name__ == "__main__":
    run()
