-- vitalStats — ingestion-owned tables
-- Creates all tables that are written to directly by Python ingestion scripts.
-- Run with: psql -d vitalstats -f infrastructure/database/create_ingestion_tables.sql
--
-- DEPENDENCY: Run init_schemas.sql first to create the raw/silver/gold schemas.
--
-- OWNERSHIP MODEL:
--   These tables are owned by the ingestion layer (ingestion/ folder).
--   They are populated by Python scripts in ingestion/google_sheets/.
--   Do NOT add Silver or Gold tables here — dbt owns those and creates
--   them automatically on first `cd dbt && uv run dbt run`.
--
-- ── RAW LAYER ─────────────────────────────────────────────────────────────
-- Append-only audit logs. Rows are never updated or deleted.
-- Each table is populated by a corresponding ingestion script.

-- Populated by: ingestion/google_sheets/extract_blood_tests.py
CREATE TABLE IF NOT EXISTS raw.blood_tests_raw (
    id                      SERIAL PRIMARY KEY,
    ingested_at             TIMESTAMP NOT NULL DEFAULT NOW(),
    source_file             TEXT NOT NULL,
    row_hash                TEXT NOT NULL,
    date_raw                TEXT,
    test_type_raw           TEXT,
    analyte_raw             TEXT,
    result_raw              TEXT,
    unit_raw                TEXT,
    reference_interval_raw  TEXT,
    collection_raw          TEXT,
    notes_raw               TEXT
);

-- Populated by: ingestion/google_sheets/extract_menoscale.py
CREATE TABLE IF NOT EXISTS raw.menoscale_raw (
    id                      SERIAL PRIMARY KEY,
    ingested_at             TIMESTAMP NOT NULL DEFAULT NOW(),
    source_file             TEXT NOT NULL,
    row_hash                TEXT NOT NULL,
    date_raw                TEXT,
    score_raw               TEXT
);


-- ── PIPELINE STATE ────────────────────────────────────────────────────────
-- Written by all ingestion scripts. Tracks current state per source
-- and full run history.

CREATE TABLE IF NOT EXISTS raw.pipeline_state (
    source                  TEXT PRIMARY KEY,
    last_run_at             TIMESTAMP,
    last_ingested_date      DATE,
    last_row_hash           TEXT,
    row_count               INTEGER,
    status                  TEXT,
    error_message           TEXT
);

CREATE TABLE IF NOT EXISTS raw.pipeline_run_log (
    run_id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source                  TEXT NOT NULL,
    started_at              TIMESTAMP NOT NULL,
    finished_at             TIMESTAMP,
    rows_fetched            INTEGER,
    rows_ingested           INTEGER,
    rows_skipped            INTEGER,
    rows_failed             INTEGER,
    rows_skipped_detail     JSONB,
    status                  TEXT NOT NULL,
    error_message           TEXT,
    error_traceback         TEXT
);

-- ── SILVER — INGESTION-OWNED ──────────────────────────────────────────────
-- stg_unknown_values is the only Silver table owned by ingestion.
-- All other Silver objects are dbt views created on first dbt run.

CREATE TABLE IF NOT EXISTS silver.stg_unknown_values (
    id                      SERIAL PRIMARY KEY,
    detected_at             TIMESTAMP NOT NULL DEFAULT NOW(),
    run_id                  UUID REFERENCES raw.pipeline_run_log(run_id),
    source                  TEXT NOT NULL,
    field                   TEXT NOT NULL,
    raw_value               TEXT NOT NULL,
    example_row             JSONB,
    risk_level              TEXT NOT NULL,
    resolved                BOOLEAN DEFAULT FALSE,
    resolved_at             TIMESTAMP,
    resolution_note         TEXT
);
