-- ─────────────────────────────────────────────────────────────────────────────
-- stg_google_sheets__menoscale_vw
--
-- Purpose : First transformation layer for MenoScale data ingested from
--           Google Sheets. Parses the raw date string into a typed DATE column,
--           casts the score to NUMERIC, and deduplicates to the latest ingested
--           version of each logical row.
--
-- Source  : raw.menoscale_raw  (append-only)
-- Output  : silver.stg_google_sheets__menoscale_vw  (view)
-- Docs    : yml_docs/_stg_google_sheets__menoscale_vw.yml
--
-- Ownership : dbt owns this object. Do not CREATE or DROP it manually.
-- ─────────────────────────────────────────────────────────────────────────────

with source as (

    -- Pull all rows from the raw audit log, including historical versions of
    -- edited rows. Deduplication to the latest version happens in the
    -- deduped CTE below.
    select * from {{ source('raw', 'menoscale_raw') }}

),

parsed as (

    -- Type-cast and parse raw string columns into structured fields.
    -- No business logic here — faithful to source values.
    -- Whitespace is trimmed on all text fields; empty strings normalised to NULL.

    select
        id,
        row_hash                                                as source_row_hash,
        ingested_at                                             as loaded_at,

        -- ── Date ─────────────────────────────────────────────────────────
        -- Source has two separator variants:
        --   "6-Sep-2024"  (D-Mon-YYYY, hyphen-separated)
        --   "16 Apr 2025" (D Mon YYYY, space-separated)
        -- regexp_replace normalises all hyphens to spaces first, producing
        -- a uniform "D Mon YYYY" string that a single to_date format handles.
        -- Returns NULL on parse failure — rows will fail the not_null dbt
        -- test and surface for investigation.
        to_date(
            nullif(trim(regexp_replace(date_raw, '-', ' ', 'g')), ''),
            'DD Mon YYYY'
        )                                                       as menoscale_date,

        -- ── Score ─────────────────────────────────────────────────────────
        -- Raw string cast to NUMERIC. Expected range 0–100.
        -- NULL if score_raw is null or blank.
        cast(score_raw as numeric)                              as menoscale_score

    from source

),

deduped as (

    -- Deduplicate to the latest ingested version of each logical menoscale row.
    --
    -- Logical key: menoscale_date
    -- A MenoScale entry is uniquely identified by when it was recorded.
    --
    -- When a source row is edited in Google Sheets and re-ingested, the new
    -- version has a later loaded_at and a different source_row_hash.
    -- row_number() = 1 selects the most recently ingested version only.
    --
    -- Rows with a NULL menoscale_date (unparseable date string) are retained here —
    -- they will fail the not_null dbt test and surface for investigation.

    select
        *,
        row_number() over (
            partition by menoscale_date
            order by loaded_at desc, id desc
        ) as _row_number

    from parsed

)

-- ── Final output ──────────────────────────────────────────────────────────────
-- Deduplicated rows only (_row_number = 1).
-- _row_number is an internal dedup column; excluded from the view output.

select
    id,
    menoscale_date,
    menoscale_score,
    source_row_hash,
    loaded_at

from deduped
where _row_number = 1
