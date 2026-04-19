"""
Shared pipeline utilities for all vitalStats ingestion scripts.

Covers: DB connection, run logging, hash-based deduplication,
column validation, and raw JSON archiving.
"""

import json
import os
from pathlib import Path
import uuid
from datetime import datetime, timezone, date

import psycopg2

# ── Database helpers ──────────────────────────────────────────────────────────


def get_db_connection():
    """
    Open a psycopg2 connection using DATABASE_URL from the environment.

    Raises:
        EnvironmentError: if DATABASE_URL is not set.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise EnvironmentError("DATABASE_URL environment variable is not set.")
    return psycopg2.connect(url)


def start_run(conn, source: str) -> str:
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
            (run_id, source, started_at),
        )
        cur.execute(
            """
            INSERT INTO raw.pipeline_state (source, last_run_at, status)
            VALUES (%s, %s, 'running')
            ON CONFLICT (source) DO UPDATE
                SET last_run_at = EXCLUDED.last_run_at,
                    status = 'running'
            """,
            (source, started_at),
        )
    conn.commit()
    return run_id


def finish_run(
    conn,
    run_id: str,
    source: str,
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
            (status, error_message, rows_ingested, source),
        )
    conn.commit()


def fail_run(conn, run_id: str, source: str, message: str, traceback: str | None = None) -> None:
    """
    Convenience wrapper for hard failures. Calls _finish_run with status='failed'.
    Defined separately so call sites read clearly: fail_run(...) rather than
    _finish_run(..., status='failed') repeated everywhere.
    """
    finish_run(
        conn,
        run_id,
        source,
        status="failed",
        error_message=message,
        error_traceback=traceback,
    )


# ── Validation helpers ────────────────────────────────────────────────────────

def get_previous_row_count(conn, source: str) -> int:
    """
    Return the row count from the last run stored in pipeline_state.
    Returns 0 if this is the first ever run (no row in pipeline_state yet).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT row_count FROM raw.pipeline_state WHERE source = %s",
            (source,),
        )
        result = cur.fetchone()
    # fetchone() returns a tuple e.g. (524,) or None if no row found.
    return result[0] if result and result[0] is not None else 0


def get_existing_hashes(conn, raw_table: str) -> set[str]:
    """
    Fetch every row hash already in raw.

    We load these into a Python set so that checking whether a hash
    already exists is O(1) — a set lookup is instant regardless of how
    many hashes are stored.
    note: fetchall() returns a list of tuples — each row is (hash_string,)
    """
    with conn.cursor() as cur:
        cur.execute(f"SELECT row_hash FROM {raw_table}")
        return {row[0] for row in cur.fetchall()}


def validate_columns(rows: list[dict], expected_columns: list[str]) -> list[str]:   # TO DO - modify and add to utils
    """
    Check that all expected columns are present.

    Returns a list of missing column names — empty if all present.
    We only need to check the first row because every row in the response
    has the same keys (padded by sheets_client).
    """
    if not rows:
        return []
    actual = set(rows[0].keys())
    expected = set(expected_columns)
    return sorted(expected - actual)


def write_raw_json(
    rows: list[dict],
    today: date,
    output_directory: Path,
    output_path: str,
) -> Path:
    """
    Archive the raw rows as JSON, organised by date.

    Path: data/raw/menoscale/YYYY-MM-DD/menoscale.json

    mkdir(parents=True, exist_ok=True) creates the full directory path
    if it doesn't already exist. parents=True means it also creates any
    intermediate directories. exist_ok=True means it won't error if the
    directory is already there.

    Returns the path written to.
    """
    out_dir = output_directory / today.isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / output_path
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2, default=str)
    return out_path
