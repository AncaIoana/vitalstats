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
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from ingestion.config.known_values import (
    EXPECTED_COLUMNS_BLOOD_TESTS,
    KNOWN_COLLECTION_SITES,
    KNOWN_TEST_TYPES,
)
from ingestion.google_sheets.extract_utils import (
    get_db_connection,
    start_run,
    finish_run,
    fail_run,
    get_previous_row_count,
    get_existing_hashes,
    validate_columns,
    write_raw_json
)
from ingestion.google_sheets.sheets_client import fetch_tab
from ingestion.utils.hashing import hash_row

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

SOURCE = "blood_tests_bulk"                 # identifies this pipeline in the DB
RAW_DIR = Path("data/raw/blood_tests")      # local archive directory
RAW_OUTPUT_PATH = "blood_tests_bulk.json"   # where to write raw JSON archive
RAW_TABLE = "raw.blood_tests_raw"           # where to insert raw rows in the DB

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
    # to clean up. Once we have a DB connection, we use fail_run instead.

    conn = get_db_connection()
    run_id = start_run(conn, SOURCE)
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
            fail_run(conn, run_id, source=SOURCE, message=msg, traceback=tb.format_exc())
            return

        log.info("Fetched %d non-empty rows", len(rows))

        # ── 2a. Validate columns ──────────────────────────────────────────────
        missing = validate_columns(rows, expected_columns=EXPECTED_COLUMNS_BLOOD_TESTS)
        if missing:
            msg = f"Missing expected columns: {missing}. Aborting."
            log.error(msg)
            fail_run(conn, run_id, source=SOURCE, message=msg)
            return

        # ── 2b. Validate row count ────────────────────────────────────────────
        previous_count = get_previous_row_count(conn, source=SOURCE)
        if len(rows) < previous_count:
            msg = (
                f"Row count dropped: expected >= {previous_count}, "
                f"got {len(rows)}. Rows may have been deleted from source."
            )
            log.error(msg)
            fail_run(conn, run_id, source=SOURCE, message=msg)
            return

        # ── 3. Hash rows, detect unknowns, split new vs duplicate ─────────────
        existing_hashes = get_existing_hashes(conn, raw_table=RAW_TABLE)
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
                fail_run(conn, run_id, source=SOURCE, message=msg)
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
        out_path = write_raw_json(rows, today, output_directory=RAW_DIR, output_path=RAW_OUTPUT_PATH)
        log.info("Raw JSON written to %s", out_path)

        # ── 5. Insert new rows into DB (single transaction) ───────────────────
        # All inserts happen inside one transaction. If any insert fails,
        # the entire batch is rolled back — no partial loads.
        with conn.cursor() as cur:
            for row in new_rows:
                row_hash = row.pop("_hash")
                cur.execute(
                    f"""
                    INSERT INTO {RAW_TABLE} (
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
        log.info("Inserted %d rows into %s", len(new_rows), RAW_TABLE)

        # ── 6. Finalise pipeline state ────────────────────────────────────────
        final_status = "partial" if has_unknown_site else "success"
        finish_run(
            conn,
            run_id,
            source=SOURCE,
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
            fail_run(conn, run_id, source=SOURCE, message=msg, traceback=tb.format_exc())
        except Exception:
            pass  # if the DB itself is broken, nothing we can do

    finally:
        conn.close()


if __name__ == "__main__":
    run()
