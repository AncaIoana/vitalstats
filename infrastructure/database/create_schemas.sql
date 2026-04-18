-- vitalStats — local database setup
-- Run with: psql -d vitalstats -f infrastructure/database/create_schemas.sql

-- ── Schemas ───────────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- ── RAW LAYER ─────────────────────────────────────────────────────────────

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

CREATE TABLE IF NOT EXISTS raw.menoscale_raw (                                                           
    id                   SERIAL PRIMARY KEY,
    ingested_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    source_file          TEXT NOT NULL,                     
    row_hash             TEXT NOT NULL,                     
    date_raw             TEXT,                              
    score_raw            TEXT
);

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

-- ── SILVER LAYER ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS silver.stg_blood_tests (
    stg_id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_date               DATE NOT NULL,
    test_type               TEXT NOT NULL,
    analyte_name            TEXT NOT NULL,
    analyte_slug            TEXT NOT NULL,
    result_numeric          NUMERIC(10, 4),
    result_text             TEXT,
    result_is_numeric       BOOLEAN NOT NULL,
    unit                    TEXT,
    unit_normalised         TEXT,
    result_normalised       NUMERIC(10, 4),
    ref_low                 NUMERIC(10, 4),
    ref_high                NUMERIC(10, 4),
    ref_type                TEXT,
    ref_text_raw            TEXT,
    collection_site         TEXT,
    notes                   TEXT,
    is_duplicate            BOOLEAN NOT NULL DEFAULT FALSE,
    source_row_hash         TEXT NOT NULL,
    loaded_at               TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stg_bt_date
    ON silver.stg_blood_tests(test_date);
CREATE INDEX IF NOT EXISTS idx_stg_bt_analyte
    ON silver.stg_blood_tests(analyte_slug);
CREATE INDEX IF NOT EXISTS idx_stg_bt_date_analyte
    ON silver.stg_blood_tests(test_date, analyte_slug);

CREATE TABLE IF NOT EXISTS silver.stg_menoscale (
    stg_id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recorded_date           DATE NOT NULL,
    total_score             NUMERIC(6, 2),
    notes                   TEXT,
    source_row_hash         TEXT NOT NULL,
    loaded_at               TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS silver.stg_medications (
    stg_id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    medication_name         TEXT NOT NULL,
    medication_slug         TEXT NOT NULL,
    dosage_raw              TEXT,
    dosage_value            NUMERIC(10, 4),
    dosage_unit             TEXT,
    start_date              DATE NOT NULL,
    end_date                DATE,
    is_ongoing              BOOLEAN NOT NULL DEFAULT FALSE,
    frequency_per_day       NUMERIC(4, 2),
    is_active               BOOLEAN NOT NULL,
    notes                   TEXT,
    source_row_hash         TEXT NOT NULL,
    loaded_at               TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stg_med_slug
    ON silver.stg_medications(medication_slug);
CREATE INDEX IF NOT EXISTS idx_stg_med_dates
    ON silver.stg_medications(start_date, end_date);

CREATE TABLE IF NOT EXISTS silver.stg_vaccines (
    stg_id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vaccine_name            TEXT NOT NULL,
    vaccine_slug            TEXT NOT NULL,
    date_administered              DATE NOT NULL,
    immunity_duration_text  TEXT,
    booster_due_year        INTEGER,
    booster_due_date        DATE,
    notes                   TEXT,
    source_row_hash         TEXT NOT NULL,
    loaded_at               TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stg_vax_slug
    ON silver.stg_vaccines(vaccine_slug);
CREATE INDEX IF NOT EXISTS idx_stg_vax_date
    ON silver.stg_vaccines(date_administered);

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

-- ── GOLD LAYER ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS gold.mart_blood_trends (
    analyte_slug            TEXT NOT NULL,
    analyte_name            TEXT NOT NULL,
    test_type               TEXT NOT NULL,
    test_date               DATE NOT NULL,
    result_normalised       NUMERIC(10, 4),
    unit_normalised         TEXT,
    ref_low                 NUMERIC(10, 4),
    ref_high                NUMERIC(10, 4),
    is_in_range             BOOLEAN,
    is_flagged_high         BOOLEAN,
    is_flagged_low          BOOLEAN,
    collection_site         TEXT,
    rolling_avg_3m          NUMERIC(10, 4),
    rolling_avg_6m          NUMERIC(10, 4),
    personal_mean           NUMERIC(10, 4),
    personal_stddev         NUMERIC(10, 4),
    z_score                 NUMERIC(6, 3),
    is_personal_anomaly     BOOLEAN,
    trend_direction         TEXT,
    reading_count           INTEGER,
    PRIMARY KEY (analyte_slug, test_date)
);

CREATE TABLE IF NOT EXISTS gold.mart_health_timeline (
    event_id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_date              DATE NOT NULL,
    event_type              TEXT NOT NULL,
    source_system           TEXT NOT NULL,
    category                TEXT,
    metric_name             TEXT,
    metric_value_numeric    NUMERIC(12, 4),
    metric_value_text       TEXT,
    metric_unit             TEXT,
    is_flagged              BOOLEAN,
    flag_reason             TEXT,
    notes                   TEXT,
    created_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_timeline_date
    ON gold.mart_health_timeline(event_date);
CREATE INDEX IF NOT EXISTS idx_timeline_type
    ON gold.mart_health_timeline(event_type);
CREATE INDEX IF NOT EXISTS idx_timeline_metric
    ON gold.mart_health_timeline(metric_name);

CREATE TABLE IF NOT EXISTS gold.mart_reference_ranges (
    analyte_slug            TEXT PRIMARY KEY,
    analyte_name            TEXT NOT NULL,
    test_type               TEXT NOT NULL,
    canonical_unit          TEXT NOT NULL,
    ref_low                 NUMERIC(10, 4),
    ref_high                NUMERIC(10, 4),
    ref_type                TEXT NOT NULL,
    source                  TEXT,
    notes                   TEXT,
    updated_at              TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS gold.mart_analyte_reference (
    analyte_slug            TEXT PRIMARY KEY,
    analyte_name            TEXT NOT NULL,
    description             TEXT,
    what_it_measures        TEXT,
    high_means              TEXT,
    low_means               TEXT,
    related_organs          TEXT[],
    related_conditions      TEXT[],
    source_name             TEXT,
    source_url              TEXT,
    retrieved_at            TIMESTAMP,
    updated_at              TIMESTAMP NOT NULL DEFAULT NOW()
);
