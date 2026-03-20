# Database Schema — vitalStats Platform

## Architecture: Medallion Pattern

```
S3 (Bronze / Raw)  →  PostgreSQL Silver (Staging)  →  PostgreSQL Gold (Marts)
```

All dbt models live in PostgreSQL. Raw files (original CSVs, API responses) are archived in S3.

---

## PostgreSQL Schemas

| Schema | Purpose | dbt layer |
|---|---|---|
| `raw` | Loaded directly from source, minimal transformation | Loaded by Python ingestion scripts |
| `silver` | Cleaned, typed, deduplicated, normalised | dbt staging + intermediate models |
| `gold` | Analytics-ready, ML-ready, business logic applied | dbt mart models |

---

## Bronze Layer — S3 Archive

All raw files are stored in S3 before loading into PostgreSQL. This is your safety net — you can always re-derive everything from here.

```
s3://vitalStats-raw/
├── blood_tests/
│   ├── 2026-03-01/blood_tests_bulk.csv      ← timestamped snapshots
│   └── 2026-03-08/blood_tests_bulk.csv
├── menoscale/
│   └── 2026-03-01/menoscale.csv
├── fitbit/                                   ← Phase 4
├── flo/                                      ← Phase 4
├── medications_vaccines/                      ← Phase 1b
├── medical_letters/                          ← Phase 4
└── health_connect/                           ← Phase 4
```

---

## Silver Layer — PostgreSQL

### `raw.blood_tests_raw`
Direct load from CSV. No transformations. Preserves source exactly.

```sql
CREATE TABLE raw.blood_tests_raw (
    id                   SERIAL PRIMARY KEY,
    ingested_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    source_file          TEXT NOT NULL,                     -- filename or S3 key
    row_hash             TEXT NOT NULL,                     -- SHA256 of all fields for dedup
    date_raw             TEXT,                              -- "6-Apr-2023" — as-is from source
    test_type_raw        TEXT,
    analyte_raw          TEXT,
    result_raw           TEXT,                              -- "< 0.6", "negative", "48" — as-is
    unit_raw             TEXT,
    reference_interval_raw TEXT,
    collection_raw       TEXT,
    notes_raw            TEXT
);
```

---

### `silver.stg_blood_tests`
Cleaned and typed. One row per analyte per date per collection site.

```sql
CREATE TABLE silver.stg_blood_tests (
    stg_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_date            DATE NOT NULL,                     -- parsed from "6-Apr-2023"
    test_type            TEXT NOT NULL,                     -- "Biochemistry", "Hematology", etc.
    analyte_name         TEXT NOT NULL,                     -- cleaned analyte name
    analyte_slug         TEXT NOT NULL,                     -- "alt_alanine_aminotransferase"
    result_numeric       NUMERIC(10, 4),                    -- NULL if non-numeric result
    result_text          TEXT,                              -- "negative", "Not Detected", etc.
    result_is_numeric    BOOLEAN NOT NULL,
    unit                 TEXT,
    unit_normalised      TEXT,                              -- canonical unit after conversion
    result_normalised    NUMERIC(10, 4),                    -- result converted to canonical unit
    ref_low              NUMERIC(10, 4),                    -- parsed lower bound
    ref_high             NUMERIC(10, 4),                    -- parsed upper bound
    ref_type             TEXT,                              -- "range", "lt", "gt", "categorical"
    ref_text_raw         TEXT,                              -- original reference interval string
    collection_site      TEXT,                              -- "New Islington", "Salford Royal", "Synevo"
    notes                TEXT,
    is_duplicate         BOOLEAN NOT NULL DEFAULT FALSE,
    source_row_hash      TEXT NOT NULL,                     -- FK to raw table
    loaded_at            TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_bt_date ON silver.stg_blood_tests(test_date);
CREATE INDEX idx_stg_bt_analyte ON silver.stg_blood_tests(analyte_slug);
CREATE INDEX idx_stg_bt_date_analyte ON silver.stg_blood_tests(test_date, analyte_slug);
```

**Key transformation logic in dbt:**
- Parse `"6-Apr-2023"` → `DATE`
- Parse `"< 0.6"` → `result_numeric = 0.6`, `ref_type = "lt"`
- Convert `mg/dL` ↔ `mmol/L` for analytes measured in both (cholesterol, glucose, calcium)
- Generate `analyte_slug` for consistent joining: `lower(regexp_replace(analyte_name, '[^a-zA-Z0-9]', '_', 'g'))`
- Detect duplicates via `row_hash` comparison

---

### `silver.stg_menoscale`
Cleaned menoscale scores.

```sql
CREATE TABLE silver.stg_menoscale (
    stg_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recorded_date        DATE NOT NULL,
    total_score          NUMERIC(6, 2),
    -- individual symptom columns to be confirmed once tab structure is shared
    notes                TEXT,
    source_row_hash      TEXT NOT NULL,
    loaded_at            TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

### `silver.stg_fitbit_daily` *(Phase 4)*
```sql
CREATE TABLE silver.stg_fitbit_daily (
    stg_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    activity_date        DATE NOT NULL,
    steps                INTEGER,
    active_minutes       INTEGER,
    sedentary_minutes    INTEGER,
    calories_burned      INTEGER,
    resting_heart_rate   NUMERIC(5, 1),
    hrv_daily_rmssd      NUMERIC(6, 2),
    spo2_avg             NUMERIC(4, 1),
    loaded_at            TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### `silver.stg_fitbit_sleep` *(Phase 4)*
```sql
CREATE TABLE silver.stg_fitbit_sleep (
    stg_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sleep_date           DATE NOT NULL,                     -- date of waking
    total_sleep_minutes  INTEGER,
    deep_sleep_minutes   INTEGER,
    light_sleep_minutes  INTEGER,
    rem_sleep_minutes    INTEGER,
    awake_minutes        INTEGER,
    sleep_score          INTEGER,
    sleep_start_time     TIMESTAMP,
    sleep_end_time       TIMESTAMP,
    loaded_at            TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

### `silver.stg_flo_cycles` *(Phase 4)*
```sql
CREATE TABLE silver.stg_flo_cycles (
    stg_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_start_date     DATE NOT NULL,
    cycle_end_date       DATE,
    cycle_length_days    INTEGER,
    period_length_days   INTEGER,
    phase                TEXT,           -- "menstruation" | "follicular" | "ovulatory" | "luteal"
    source_row_hash      TEXT NOT NULL,
    loaded_at            TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### `silver.stg_flo_symptoms` *(Phase 4)*
```sql
CREATE TABLE silver.stg_flo_symptoms (
    stg_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    logged_date          DATE NOT NULL,
    symptom_category     TEXT,           -- "physical" | "mood" | "energy" | "digestion" etc.
    symptom_name         TEXT NOT NULL,  -- "cramps" | "bloating" | "headache" | "fatigue" etc.
    severity             TEXT,           -- if recorded by Flo
    cycle_phase          TEXT,           -- derived: which phase this date falls in
    source_row_hash      TEXT NOT NULL,
    loaded_at            TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

### `silver.stg_medications`
One row per medication period. Same medication appears multiple times as dosage or frequency changes over time.

```sql
CREATE TABLE silver.stg_medications (
    stg_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    medication_name      TEXT NOT NULL,
    medication_slug      TEXT NOT NULL,                     -- "metyrapone", "ferrous_sulfate" etc.
    dosage_raw           TEXT,                              -- "250mg", "1500mg/400unit" — as-is from source
    dosage_value         NUMERIC(10, 4),                    -- parsed numeric component
    dosage_unit          TEXT,                              -- "mg", "mg/unit" etc.
    start_date           DATE NOT NULL,
    end_date             DATE,                              -- NULL = ongoing
    is_ongoing           BOOLEAN NOT NULL DEFAULT FALSE,
    frequency_per_day    NUMERIC(4, 2),                     -- 0 = paused/stopped; 0.5 = alternate days
    is_active            BOOLEAN NOT NULL,
    notes                TEXT,
    source_row_hash      TEXT NOT NULL,
    loaded_at            TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_med_slug ON silver.stg_medications(medication_slug);
CREATE INDEX idx_stg_med_dates ON silver.stg_medications(start_date, end_date);
```

**Key transformation logic:**
- Normalise names to slugs: `"Ferrous sulfade"` → `ferrous_sulfate` (fix typo in source)
- Parse dosage: `"250mg"` → `dosage_value = 250`, `dosage_unit = "mg"`
- Known bad date: `"15-Feb-0204"` → correct to `2024-02-15`
- `is_active = TRUE` where `frequency_per_day > 0 AND (end_date IS NULL OR end_date >= CURRENT_DATE)`

---

### `silver.stg_vaccines`
One row per vaccine administration. Anca rows only — Lukasz rows filtered out at ingestion.

```sql
CREATE TABLE silver.stg_vaccines (
    stg_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vaccine_name         TEXT NOT NULL,
    vaccine_slug         TEXT NOT NULL,                     -- "flu_influenza", "covid_19", "dtp" etc.
    date_given           DATE NOT NULL,
    immunity_duration_text TEXT,                            -- "1 year", "Lifelong", "Part of 3-dose course"
    booster_due_year     INTEGER,                           -- parsed from 2028.0 → 2028
    booster_due_date     DATE,                              -- derived: YYYY-01-01 from booster_due_year
    notes                TEXT,
    source_row_hash      TEXT NOT NULL,
    loaded_at            TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_stg_vax_slug ON silver.stg_vaccines(vaccine_slug);
CREATE INDEX idx_stg_vax_date ON silver.stg_vaccines(date_given);
```

**Key transformation logic:**
- Filter: only ingest rows WHERE `Name = 'Anca'` — Lukasz rows discarded at staging
- Strip trailing spaces: `"Covid-19 "` → `"Covid-19"`
- Parse booster_due integer: `2028.0` → `booster_due_year = 2028`, `booster_due_date = 2028-01-01`
- Unparseable booster_due (e.g. `"See 3rd dose date"`) → both NULL, value stored in notes

---

## Gold Layer — PostgreSQL

### `gold.mart_blood_trends`
One row per analyte per test date. The primary analytics table for blood tests.

```sql
CREATE TABLE gold.mart_blood_trends (
    analyte_slug         TEXT NOT NULL,
    analyte_name         TEXT NOT NULL,
    test_type            TEXT NOT NULL,
    test_date            DATE NOT NULL,
    result_normalised    NUMERIC(10, 4),
    unit_normalised      TEXT,
    ref_low              NUMERIC(10, 4),
    ref_high             NUMERIC(10, 4),
    is_in_range          BOOLEAN,
    is_flagged_high      BOOLEAN,
    is_flagged_low       BOOLEAN,
    collection_site      TEXT,

    -- rolling statistics (computed in dbt)
    rolling_avg_3m       NUMERIC(10, 4),                    -- 3-month rolling average
    rolling_avg_6m       NUMERIC(10, 4),
    personal_mean        NUMERIC(10, 4),                    -- your all-time mean
    personal_stddev      NUMERIC(10, 4),
    z_score              NUMERIC(6, 3),                     -- (result - personal_mean) / personal_stddev
    is_personal_anomaly  BOOLEAN,                           -- |z_score| > 2
    trend_direction      TEXT,                              -- "improving" | "stable" | "worsening" | "insufficient_data"
    reading_count        INTEGER,                           -- how many readings exist for this analyte

    PRIMARY KEY (analyte_slug, test_date)
);
```

---

### `gold.mart_health_timeline`
The unified event log. **Every data source eventually lands here.** Foundation for cross-source ML.

```sql
CREATE TABLE gold.mart_health_timeline (
    event_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_date           DATE NOT NULL,
    event_type           TEXT NOT NULL,                     -- "blood_test" | "sleep" | "activity" | "menoscale" | "medication" | "vaccine" | "medical_letter"
    source_system        TEXT NOT NULL,                     -- "google_sheets" | "fitbit" | "health_connect" | "pdf"
    category             TEXT,                              -- "Biochemistry" | "Hematology" | "lifestyle" | etc.
    metric_name          TEXT,                              -- analyte_slug or metric name
    metric_value_numeric NUMERIC(12, 4),
    metric_value_text    TEXT,
    metric_unit          TEXT,
    is_flagged           BOOLEAN,
    flag_reason          TEXT,
    notes                TEXT,
    created_at           TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_timeline_date ON gold.mart_health_timeline(event_date);
CREATE INDEX idx_timeline_type ON gold.mart_health_timeline(event_type);
CREATE INDEX idx_timeline_metric ON gold.mart_health_timeline(metric_name);
```

---

### `gold.mart_ml_features`
Flattened, wide-format feature table for ML models. One row per date, one column per metric.

```sql
-- Generated by dbt PIVOT macro — columns expand as new analytes are added
-- Example columns (not exhaustive):
CREATE TABLE gold.mart_ml_features (
    feature_date                           DATE PRIMARY KEY,

    -- Blood test features
    bt_alt_result                          NUMERIC,
    bt_alt_z_score                         NUMERIC,
    bt_alt_trend                           TEXT,
    bt_ferritin_result                     NUMERIC,
    bt_ferritin_z_score                    NUMERIC,
    bt_hba1c_result                        NUMERIC,
    -- ... one set per analyte

    -- Menoscale features (Phase 1b)
    menoscale_total_score                  NUMERIC,

    -- Flo features (Phase 4)
    flo_cycle_phase                        TEXT,       -- "menstruation" | "follicular" | "ovulatory" | "luteal"
    flo_cycle_length_days                  INTEGER,
    flo_period_length_days                 INTEGER,
    flo_days_since_period_start            INTEGER,

    -- Fitbit features (Phase 4)
    fitbit_steps                           INTEGER,
    fitbit_sleep_total_mins                INTEGER,
    fitbit_resting_hr                      NUMERIC,
    fitbit_hrv_rmssd                       NUMERIC,

    -- Medication features (Phase 1b)
    med_metyrapone_active                  BOOLEAN,        -- is metyrapone active on this date
    med_metyrapone_freq_per_day            NUMERIC,
    med_ferrous_sulfate_active             BOOLEAN,
    med_ferrous_sulfate_freq_per_day       NUMERIC,
    -- ... one set per tracked medication

    -- Vaccine features (Phase 1b)
    vax_days_since_last_flu                INTEGER,
    vax_days_since_last_covid              INTEGER,

    -- Derived features
    days_since_last_blood_test             INTEGER,
    rolling_7d_avg_steps                   NUMERIC,
    rolling_30d_avg_sleep_mins             NUMERIC
);
```

---

### `gold.mart_insights` *(Phase 3)*
Stores all LLM-generated insights with the inputs that generated them. Fully auditable.

```sql
CREATE TABLE gold.mart_insights (
    insight_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    generated_at         TIMESTAMP NOT NULL DEFAULT NOW(),
    insight_type         TEXT NOT NULL,                     -- "blood_test_summary" | "anomaly_alert" | "trend_report"
    model_used           TEXT NOT NULL,                     -- "claude-3-5-sonnet" | "gpt-4o"
    prompt_template      TEXT NOT NULL,
    prompt_rendered      TEXT NOT NULL,                     -- the actual prompt sent
    raw_response         TEXT NOT NULL,                     -- full model response
    insight_text         TEXT NOT NULL,                     -- parsed, clean insight
    flags_included       TEXT[],                            -- analytes that triggered this insight
    data_window_start    DATE,
    data_window_end      DATE,
    user_rating          INTEGER                            -- 1-5, for future ML feedback loop
);
```

---

### `gold.mart_analyte_reference`
Plain-English reference content per analyte, sourced from trusted medical sources. Used to enrich LLM prompts (RAG) and power the dashboard "what does this mean?" feature.

```sql
CREATE TABLE gold.mart_analyte_reference (
    analyte_slug         TEXT PRIMARY KEY,
    analyte_name         TEXT NOT NULL,
    description          TEXT,                              -- plain-English: "what is this?"
    what_it_measures     TEXT,                              -- "measures liver enzyme activity"
    high_means           TEXT,                              -- plain-English interpretation of high result
    low_means            TEXT,                              -- plain-English interpretation of low result
    related_organs       TEXT[],                            -- e.g. ["liver", "gallbladder"]
    related_conditions   TEXT[],                            -- e.g. ["fatty liver", "hepatitis"]
    source_name          TEXT,                              -- "NHS Inform" | "MedlinePlus" | "Lab Tests Online"
    source_url           TEXT,                              -- URL used to retrieve the content
    retrieved_at         TIMESTAMP,                         -- when the content was last fetched
    updated_at           TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

### `gold.mart_reference_ranges`
Canonical reference ranges — your single source of truth, not embedded in test rows.

```sql
CREATE TABLE gold.mart_reference_ranges (
    analyte_slug         TEXT PRIMARY KEY,
    analyte_name         TEXT NOT NULL,
    test_type            TEXT NOT NULL,
    canonical_unit       TEXT NOT NULL,
    ref_low              NUMERIC(10, 4),
    ref_high             NUMERIC(10, 4),
    ref_type             TEXT NOT NULL,                     -- "range" | "lt" | "gt"
    source               TEXT,                              -- "NHS" | "WHO" | "lab_derived"
    notes                TEXT,
    updated_at           TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

## Pipeline State Tracking

Two tables work together: `pipeline_state` always reflects the current state of each source; `pipeline_run_log` is the full historical record of every execution.

```sql
-- Current state per source — one row per source, updated on every run
CREATE TABLE raw.pipeline_state (
    source               TEXT PRIMARY KEY,                  -- "blood_tests_google_sheets"
    last_run_at          TIMESTAMP,
    last_ingested_date   DATE,                              -- latest test_date successfully ingested
    last_row_hash        TEXT,                              -- last seen row hash (for delta detection)
    row_count            INTEGER,
    status               TEXT,                              -- "success" | "failed" | "running"
    error_message        TEXT
);

-- Full run history — one row per execution, never updated, append-only
CREATE TABLE raw.pipeline_run_log (
    run_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source               TEXT NOT NULL,                     -- "blood_tests_google_sheets"
    started_at           TIMESTAMP NOT NULL,
    finished_at          TIMESTAMP,
    rows_fetched         INTEGER,                           -- total rows received from source
    rows_ingested        INTEGER,                           -- rows successfully written
    rows_skipped         INTEGER,                           -- duplicates detected and skipped
    rows_failed          INTEGER,                           -- rows that failed parsing (soft errors)
    rows_skipped_detail  JSONB,                             -- [{"row": 42, "analyte": "TSH", "reason": "..."}]
    status               TEXT NOT NULL,                     -- "success" | "failed" | "running" | "partial"
    error_message        TEXT,                              -- exception message for hard failures
    error_traceback      TEXT                               -- full traceback for hard failures
);
```

---

### `silver.stg_unknown_values`
Parking table for unrecognised values detected during ingestion. Reviewed manually and resolved before values are trusted in Gold.

```sql
CREATE TABLE silver.stg_unknown_values (
    id              SERIAL PRIMARY KEY,
    detected_at     TIMESTAMP NOT NULL DEFAULT NOW(),
    run_id          UUID REFERENCES raw.pipeline_run_log(run_id),  -- which run first detected this
    source          TEXT NOT NULL,          -- "blood_tests_google_sheets"
    field           TEXT NOT NULL,          -- "collection_site" | "analyte" | "test_type"
    raw_value       TEXT NOT NULL,          -- the unrecognised value
    example_row     JSONB,                  -- a sample row containing this value
    risk_level      TEXT NOT NULL,          -- "low" (new analyte) | "high" (new collection site)
    resolved        BOOLEAN DEFAULT FALSE,  -- set to true once handled
    resolved_at     TIMESTAMP,              -- when it was resolved
    resolution_note TEXT                    -- "mapped to synevo_bucharest" | "added to known_values.py"
);
```

**Resolution workflow:**

| Scenario | Steps | dbt command |
|---|---|---|
| New analyte | Add to `mart_reference_ranges` + `mart_analyte_reference` → run dbt | `dbt run` |
| New collection site | Update `known_values.py` → delete affected Silver rows → rebuild | `dbt run --full-refresh --select stg_blood_tests` |

After resolving either scenario:
```sql
UPDATE silver.stg_unknown_values
SET resolved = TRUE,
    resolved_at = NOW(),
    resolution_note = 'added canonical range; dbt rebuilt 2026-03-10'
WHERE id = <id>;
```

---

## Unit Normalisation Map

Key conversions applied in `silver.stg_blood_tests`:

| Analyte | Synevo unit | NHS unit | Conversion |
|---|---|---|---|
| Cholesterol (all) | mg/dL | mmol/L | ÷ 38.67 |
| Glucose | mg/dL | mmol/L | ÷ 18.02 |
| Calcium (serum) | mg/dL | mmol/L | ÷ 4.008 |
| Bilirubin | mg/dL | μmol/L | × 17.1 |
| Ferritin | ng/mL | μg/L | × 1 (same) |
| HbA1c | % | mmol/mol | (% − 2.152) ÷ 0.09148 |

Canonical units follow NHS convention (mmol/L, μmol/L, g/L etc.) as that is the majority of your data.

---

## Data Quality Rules (dbt tests)

| Model | Test | Description |
|---|---|---|
| `stg_blood_tests` | `not_null` | `test_date`, `analyte_name`, `collection_site` |
| `stg_blood_tests` | `unique` | `(test_date, analyte_slug, collection_site)` composite |
| `stg_blood_tests` | `accepted_values` | `test_type` in known categories |
| `mart_blood_trends` | custom | `z_score` must be computable when `reading_count >= 3` |
| `mart_blood_trends` | custom | `trend_direction` not null when `reading_count >= 4` |
| `mart_health_timeline` | `not_null` | `event_date`, `event_type`, `source_system` |
