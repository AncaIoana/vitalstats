"""
Menoscale ingestion script — menoscale tab.

Reads from Google Sheets, validates, deduplicates, writes raw JSON to disk,
loads into raw.menoscale_raw, and updates pipeline state.

Run with:
    uv run python -m ingestion.google_sheets.extract_menoscale
"""

import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

from ingestion.config.known_values import EXPECTED_COLUMNS_MENOSCALE
from ingestion.utils.pipeline import (
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

SOURCE = "menoscale"                    # identifies this pipeline in the DB
RAW_DIR = Path("data/raw/menoscale")    # local archive directory
RAW_OUTPUT_PATH = "menoscale.json"      # where to write raw JSON archive
RAW_TABLE = "raw.menoscale_raw"         # where to insert raw rows in the DB


# ── Validation and parsing helpers ────────────────────────────────────────────────────────


def _parse_menoscale_date(raw: str) -> date:
    """
    Parse a menoscale date string that may use one of two formats:
        "6-Sep-2024"  →  hyphen-separated
        "16 Apr 2025" →  space-separated

    We also handle full month names just in case ("April" instead of "Apr").

    datetime.strptime(string, format) tries to parse `string` using `format`.
    It raises ValueError if the string doesn't match — so we try each format
    in a loop and move on if it fails.
    """
    raw = raw.strip()
    for fmt in ("%d-%b-%Y", "%d %b %Y", "%d-%B-%Y", "%d %B %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse menoscale date: '{raw}'")


def _validate_score(raw_score: str) -> int | None:
    """
    Parse and validate a raw score string.
    
    Return an int if valid, or None if invalid. Validation rules:
    - If it can't be converted → return None  (treat as soft failure)
    - If the int is outside 0–100 → return None
    - Otherwise → return the int
    """
    try:
        raw = str(raw_score).strip()
        score = int(raw)
        if not (0 <= score <= 100):
            score = None
    except ValueError:
        score = None
        
    return score


# ── Main orchestrator ─────────────────────────────────────────────────────────

def run() -> None:
    """
    Full ingestion flow for menoscale:

        1. Fetch rows from Google Sheets
        2a. Validate columns present (hard failure → abort)
        2b. Validate row count not dropped (hard failure → abort)
        3. Hash rows, detect unknowns, split new vs duplicate
        4. Write raw JSON archive to disk
        5. Insert new rows into raw.menoscale_raw (single transaction)
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
    run_id = start_run(conn, source=SOURCE)
    log.info("Run started. run_id=%s source=%s", run_id, SOURCE)

    skipped_detail: list[dict] = []  # accumulates warnings for pipeline_run_log

    try:
        # ── 1. Fetch ──────────────────────────────────────────────────────────
        log.info("Fetching '%s' from sheet %s", SOURCE, sheet_id)
        try:
            rows = fetch_tab(sheet_id, "menoscale")
        except Exception as e:
            import traceback as tb
            msg = f"Failed to fetch from Google Sheets: {e}"
            log.error(msg)
            fail_run(conn, run_id, source=SOURCE, message=msg, traceback=tb.format_exc())
            return

        log.info("Fetched %d non-empty rows", len(rows))

        # ── 2a. Validate columns ──────────────────────────────────────────────
        missing = validate_columns(rows, expected_columns=EXPECTED_COLUMNS_MENOSCALE)
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

        # ── 3. Hash rows, validate, split new vs duplicate ────────────────────
        existing_hashes = get_existing_hashes(conn, raw_table=RAW_TABLE)
        new_rows: list[dict] = []
        duplicates: int = 0
        rows_failed: int = 0

        for row in rows:
            row_hash = hash_row(row)
            
            # Parse the date
            try:
                _parse_menoscale_date(row.get("Date", ""))
            except ValueError:
                skipped_detail.append({
                    "type": "unparseable_date",
                    "field": "Date",
                    "row": {k: str(v) for k, v in row.items()},
                })
                rows_failed += 1
                log.warning("Skipping row with unparseable date: %s", row.get("Date"))
                continue
            
            # Validate the score
            raw_score = row.get("Score (out of 100)")
            score = _validate_score(raw_score or "")
            if score is None:
                skipped_detail.append({
                    "type": "invalid_score",
                    "field": "Score (out of 100)",
                    "row": {k: str(v) for k, v in row.items()},
                })
                rows_failed += 1
                log.warning("Skipping row with invalid score: %s", raw_score)
                continue

            # Skip rows already in the DB (hash-based dedup)
            if row_hash in existing_hashes:
                duplicates += 1
                continue

            new_rows.append({**row, "_hash": row_hash})

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
                    """
                    INSERT INTO raw.menoscale_raw (
                        source_file, row_hash, date_raw, score_raw
                    ) VALUES (%s, %s, %s, %s)
                    """,
                    (
                        str(out_path),
                        row_hash,
                        row.get("Date"),
                        row.get("Score (out of 100)"),
                    ),
                )
        conn.commit()
        log.info("Inserted %d rows into raw.menoscale_raw", len(new_rows))

        # ── 6. Finalise pipeline state ────────────────────────────────────────
        final_status = "partial" if skipped_detail else "success"
        finish_run(
            conn,
            run_id,
            source=SOURCE,
            status=final_status,
            rows_fetched=len(rows),
            rows_ingested=len(new_rows),
            rows_skipped=duplicates,
            rows_failed=rows_failed,
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
