-- ─────────────────────────────────────────────────────────────────────────────
-- stg_google_sheets__blood_tests_vw
--
-- Purpose : First transformation layer for blood test data ingested from
--           Google Sheets. Parses raw strings into typed columns, generates
--           canonical analyte slugs, and deduplicates to the latest version
--           of each logical row.
--
-- Source  : raw.blood_tests_raw  (append-only audit log — see ADR-005)
-- Output  : silver.stg_google_sheets__blood_tests_vw  (view)
-- Docs    : yml_docs/_stg_google_sheets__blood_tests_vw.yml
--
-- Ownership : dbt owns this object. Do not CREATE or DROP it manually.
-- ─────────────────────────────────────────────────────────────────────────────

with source as (

    -- Pull all rows from the raw audit log, including historical versions of
    -- edited rows. Deduplication to the latest version happens in the
    -- deduped CTE below.
    select * from {{ source('raw', 'blood_tests_raw') }}

),

parsed as (

    -- Type-cast and parse raw string columns into structured fields.
    -- No business logic or slug mapping here — faithful to source values.
    -- Whitespace is trimmed on all text fields; empty strings normalised to NULL.

    select
        id,
        row_hash                                                as source_row_hash,
        ingested_at                                             as loaded_at,

        -- ── Date ─────────────────────────────────────────────────────────
        -- Source format: "6-Apr-2023" (D-Mon-YYYY).
        -- Returns NULL on parse failure — rows will fail the not_null dbt
        -- test and surface for investigation.
        to_date(
            nullif(trim(date_raw), ''), 'DD-Mon-YYYY'
        )                                                       as test_date,

        -- ── Test type ────────────────────────────────────────────────────
        -- Lowercase and trim only. Values validated against known_values.py
        -- by the ingestion pipeline before reaching this table.
        lower(trim(test_type_raw))                              as test_type,

        -- ── Analyte name ─────────────────────────────────────────────────
        -- Cleaned original name preserved for display and audit purposes.
        -- Slug mapping happens in the slugged CTE.
        trim(analyte_raw)                                       as analyte_name,

        -- ── Result qualifier ─────────────────────────────────────────────
        -- Detects < or > prefix before a numeric value.
        -- Full-width variants (< >) included for defensive robustness.
        case
            when result_raw ~ '^[<＜]\s*[0-9]' then 'lt'
            when result_raw ~ '^[>＞]\s*[0-9]' then 'gt'
            else null
        end                                                     as result_qualifier,

        -- ── result_is_numeric ─────────────────────────────────────────────
        -- TRUE only when the entire value (ignoring qualifier prefix and
        -- surrounding whitespace) resolves to a plain number.
        -- Categorical strings ("negative", "Not Detected") return FALSE.
        case
            when result_raw ~ '^[<>＜＞]?\s*[0-9]+\.?[0-9]*$' then true
            else false
        end                                                     as result_is_numeric,

        -- ── result_numeric ────────────────────────────────────────────────
        -- Strips qualifier prefix and casts to NUMERIC.
        -- Handles: "140", "3.7", "< 5.0", ">120".
        -- NULL for categorical values ("negative", "Not Detected", etc.).
        case
            when result_raw ~ '^[<>＜＞]?\s*[0-9]+\.?[0-9]*$'
                then regexp_replace(result_raw, '[^0-9.]', '', 'g')::numeric
            else null
        end                                                     as result_numeric,

        -- ── result_text ───────────────────────────────────────────────────
        -- Normalised lowercase slug for categorical results.
        -- NULL when the result is numeric (result_is_numeric = TRUE).
        case
            when result_raw !~ '^[<>＜＞]?\s*[0-9]+\.?[0-9]*$'
                then lower(regexp_replace(trim(result_raw), '\s+', '_', 'g'))
            else null
        end                                                     as result_text,

        -- ── Units ─────────────────────────────────────────────────────────
        -- Pass through raw unit unchanged.
        -- Normalisation (mg/dL → mmol/L etc.) is applied in:
        --   int_google_sheets__blood_tests_normalised_vw
        nullif(trim(unit_raw), '')                              as unit,
        null::text                                              as unit_normalised,    -- populated in intermediate
        null::numeric                                           as result_normalised,  -- populated in intermediate

        -- ── Reference interval — type classification ──────────────────────
        -- Classifies the format of the raw reference interval string.
        -- Complex/narrative formats are stored verbatim in ref_text_raw
        -- for manual review and future RAG enrichment (Phase 3).
        case
            when reference_interval_raw is null
              or trim(reference_interval_raw) = ''              then 'unknown'
            when reference_interval_raw ~* '^\s*n\/?a\s*$'      then 'not_applicable'
            when trim(reference_interval_raw) ~*
                    '^\s*(negative|positive|not\s+detected|detected|reactive|non[- ]reactive)\s*$'
                then 'categorical'
            when reference_interval_raw ~ '^[<＜]\s*[0-9]'      then 'lt'
            when reference_interval_raw ~ '^[>＞]\s*[0-9]'      then 'gt'
            when reference_interval_raw
                ~ '[0-9]+\.?[0-9]*\s*-\s*[0-9]+\.?[0-9]*'     then 'range'
            else 'narrative'
        end                                                     as ref_type,

        -- ── ref_low ───────────────────────────────────────────────────────
        -- Lower bound: first number in a range, or the threshold for gt.
        case
            when reference_interval_raw
                ~ '[0-9]+\.?[0-9]*\s*-\s*[0-9]+\.?[0-9]*'
                then (regexp_match(
                    reference_interval_raw,
                    '([0-9]+\.?[0-9]*)\s*-\s*[0-9]+\.?[0-9]*'
                ))[1]::numeric
            when reference_interval_raw ~ '^[>＞]\s*([0-9]+\.?[0-9]*)'
                then (regexp_match(
                    reference_interval_raw,
                    '^[>＞]\s*([0-9]+\.?[0-9]*)'
                ))[1]::numeric
            else null
        end                                                     as ref_low,

        -- ── ref_high ──────────────────────────────────────────────────────
        -- Upper bound: second number in a range, or the threshold for lt.
        case
            when reference_interval_raw
                ~ '[0-9]+\.?[0-9]*\s*-\s*[0-9]+\.?[0-9]*'
                then (regexp_match(
                    reference_interval_raw,
                    '[0-9]+\.?[0-9]*\s*-\s*([0-9]+\.?[0-9]*)'
                ))[1]::numeric
            when reference_interval_raw ~ '^[<＜]\s*([0-9]+\.?[0-9]*)'
                then (regexp_match(
                    reference_interval_raw,
                    '^[<＜]\s*([0-9]+\.?[0-9]*)'
                ))[1]::numeric
            else null
        end                                                     as ref_high,

        -- Always preserve the original string for audit and for narrative
        -- intervals that cannot be parsed into ref_low / ref_high.
        nullif(trim(reference_interval_raw), '')                as ref_text_raw,

        -- ── Collection site / notes ───────────────────────────────────────
        nullif(trim(collection_raw), '')                        as collection_site,
        nullif(trim(notes_raw), '')                             as notes

    from source

),

slugged as (

    -- Map raw analyte names to canonical slugs.
    --
    -- Design decisions:
    --   • WHEN conditions compare trim(analyte_name) — the cleaned original
    --     string from parsed CTE, not a slugified version. This avoids running
    --     regexp_replace in every branch and keeps conditions readable.
    --   • Multiple raw names for the same analyte (lab variants, legacy names,
    --     Romanian synonyms, corrected source typos) map to the same slug.
    --   • The ELSE fallback auto-generates a slug for any unmapped analyte so
    --     new analytes are never silently dropped. They surface in
    --     stg_unknown_values via the ingestion pipeline and should be added
    --     to this CASE once reviewed and given a canonical slug.
    --   • Analytes are grouped by clinical category for maintainability.

    select
        p.*,

        case trim(p.analyte_name)

            -- ── Liver / biliary ───────────────────────────────────────────
            when 'ALT (Alanine aminotransferase)'                          then 'alt'
            when 'AST (Aspartate aminotransferase)'                        then 'ast'
            when 'Alkaline phosphatase (serum)'                            then 'alkaline_phosphatase'
            when 'GGT (gamma-glutamyl transferase) serum'                  then 'ggt'
            when 'Bilirubin (serum)'                                       then 'bilirubin'
            when 'Bilirubin total'                                         then 'bilirubin'
            when 'Total bilirubin'                                         then 'bilirubin'  -- legacy name
            when 'Albumin (serum)'                                         then 'albumin'
            when 'Globulin (serum)'                                        then 'globulin'
            when 'Protein'                                                 then 'protein_total'
            when 'Protein - total (serum)'                                 then 'protein_total'

            -- ── Lipids ────────────────────────────────────────────────────
            when 'Cholesterol total'                                       then 'cholesterol_total'
            when 'Cholesterol total (serum)'                               then 'cholesterol_total'
            when 'Cholesterol HDL (serum)'                                 then 'hdl'
            when 'Cholesterol LDL (calculated)'                            then 'ldl_calculated'
            when 'Cholesterol LDL (serum)'                                 then 'ldl_serum'
            when 'Cholesterol VLDL (calculated)'                           then 'cholesterol_vldl'
            when 'Cholesterol (non-HDL)'                                   then 'cholesterol_non_hdl'
            when 'Cholesterol (serum) / HDL ratio'                         then 'hdl_ratio'
            when 'Triglycerides'                                           then 'triglycerides'

            -- ── Kidney / electrolytes ──────────────────────────────────────
            when 'Creatinine (serum)'                                      then 'creatinine'
            when 'eGFR (estimated glomerular filtration rate)'             then 'egfr'
            when 'eGFRcreat (CKD-EPI)'                                    then 'ckd_epi'
            when 'Acute Kidney Injury (AKI) Score'                         then 'aki_score'
            when 'Urea'                                                    then 'urea'
            when 'Urea (serum)'                                            then 'urea'
            when 'Urea Nitrogen (BUN)'                                     then 'bun'
            when 'Sodium (serum)'                                          then 'sodium'
            when 'Potassium (serum)'                                       then 'potassium'
            when 'Phosphate (serum)'                                       then 'phosphate'
            when 'Serum inorganic phosphate'                               then 'phosphate'
            when 'Magnesium serum'                                         then 'magnesium'

            -- ── Calcium ────────────────────────────────────────────────────
            when 'Calcium (serum)'                                         then 'calcium_serum'
            when 'Calcium (corrected)'                                     then 'calcium_adjusted'
            when 'Calcium adjusted level'                                  then 'calcium_adjusted'
            when 'Calcium (ionic)'                                         then 'calcium_ionic'

            -- ── Full blood count ───────────────────────────────────────────
            when 'Hemoglobin'                                              then 'haemoglobin'
            when 'Haematocrit (HCT)'                                       then 'hct'
            when 'Red blood cell (RBC) count (erythrocytes / eritrocite)'  then 'rbc_count'
            when 'White blood cell count WBC (Leukocyte count)'            then 'wbc'
            when 'Platelet count (numar trombocite)'                       then 'platelet_count'
            when 'Mean corpuscular volume (MCV)'                           then 'mcv'
            when 'Mean corpuscular hemoglobin (MCH)'                       then 'mch'
            when 'Mean corpuscular hemoglobin concentration (MCHC)'        then 'mchc'
            when 'Mean platelet volume (MPV)'                              then 'mpv'
            when 'Platelet distribution width (PDW)'                       then 'pdw'
            when 'Red cell distribution width (RDW)'                       then 'rdw'
            when 'Nucleated red blood cell count'                          then 'nrbc_count'

            -- ── White cell differential ────────────────────────────────────
            when 'Neutrophil count'                                        then 'neutrophil_count'
            when 'Neutrophils'                                             then 'neutrophil_count'
            when 'Lymphocyte count'                                        then 'lymphocyte_count'
            when 'Lymphocytes'                                             then 'lymphocyte_count'
            when 'Monocytes'                                               then 'monocyte_count'
            when 'Eosinophil count'                                        then 'eosinophil_count'
            when 'Eosinophil count raised'                                 then 'eosinophil_count'
            when 'Eosinophils'                                             then 'eosinophil_count'
            when 'Basophil count'                                          then 'basophil_count'
            when 'Basophils'                                               then 'basophil_count'
            when 'Immature granulocytes count'                             then 'immature_granulocytes'

            -- ── Reticulocytes ──────────────────────────────────────────────
            when 'Reticulocytes'                                           then 'reticulocyte_count'
            when 'Reticulocyte hemoglobin equivalent (RET-He)'             then 'ret_he'
            when 'Immature reticulocyte fraction'                          then 'immature_reticulocyte_fraction'

            -- ── Iron studies ───────────────────────────────────────────────
            when 'Ferritin (serum)'                                        then 'ferritin'
            when 'Iron serum (sideremia)'                                  then 'iron_serum'
            when 'Serum iron level'                                        then 'iron_serum'
            when 'Transferrin (serum)'                                     then 'transferrin'
            when 'Transferrin saturation index'                            then 'transferrin_saturation'
            when 'Serum ceruloplasmin'                                     then 'ceruloplasmin'

            -- ── Glucose / HbA1c ────────────────────────────────────────────
            when 'Glucose serum'                                           then 'glucose'
            when 'Hemoglobin A1c (HbA1c) - past 2-3 months'               then 'hba1c'

            -- ── Thyroid ────────────────────────────────────────────────────
            when 'TSH (Thyroid-stimulating hormone)'                       then 'tsh'
            when 'FT4 (Free Thyroxine / Free T4)'                          then 'ft4'
            when 'FT4 (Tiroxina)'                                          then 'ft4'  -- Romanian synonym
            when 'Anti-TPO (thyroid peroxidase antibodies)'                then 'anti_tpo'

            -- ── Adrenal / cortisol ─────────────────────────────────────────
            when 'Cortisol (serum)'                                        then 'cortisol_serum'
            when 'Cortisol (salivary)'                                     then 'cortisol_salivary'
            when 'Cortisone (salivary)'                                    then 'cortisone_salivary'
            when 'Urine free cortisol'                                     then 'cortisol_urine_free'
            when 'Urine free cortisol excretion rate'                      then 'cortisol_urine_excretion_rate'
            when 'ONDST cortisol'                                          then 'ondst_cortisol'
            when 'ACTH'                                                    then 'acth'

            -- ── Reproductive hormones ──────────────────────────────────────
            when 'Androstenedione'                                         then 'androstenedione'
            when 'Testosterone'                                            then 'testosterone'
            when 'SHBG (Sex Hormone-Binding Globulin)'                     then 'shbg'
            when 'Free Androgen Index (FAI)'                               then 'fai'
            when 'Prolactin'                                               then 'prolactin'
            when 'Estradiol (serum)'                                       then 'estradiol'
            when 'FSH'                                                     then 'fsh'
            when 'LH'                                                      then 'lh'

            -- ── Growth factors / bone ──────────────────────────────────────
            when 'IGF-1'                                                   then 'igf1'
            when 'GF-1'                                                    then 'igf1'  -- source typo for IGF-1
            when 'Plasma parathyroid hormone level'                        then 'pth'

            -- ── Vitamins / minerals ────────────────────────────────────────
            when 'Vitamin D  25-OH (serum)'                                then 'vitamin_d'
            when 'Vitamin D2  25-OH (serum)'                               then 'vitamin_d2'
            when 'Vitamin D3 25-HO (serum)'                                then 'vitamin_d3'
            when 'Vitamin B12 (serum)'                                     then 'vitamin_b12'
            when 'Folate (serum)'                                          then 'folate'
            when 'Copper (blood)'                                          then 'copper'

            -- ── Omega-3 fatty acids ────────────────────────────────────────
            when 'Index Omega 3'                                           then 'omega3_index'
            when 'Docosahexaenoic acid (DHA)'                              then 'omega3_dha'
            when 'Eicosapentaenoic acid (EPA)'                             then 'omega3_epa'

            -- ── Coagulation ────────────────────────────────────────────────
            when 'aPTT'                                                    then 'aptt'
            when 'INR'                                                     then 'inr'
            when 'Prothrombin time (Quick)'                                then 'prothrombin_time'
            when 'Prothrombin percent'                                     then 'prothrombin_percent'

            -- ── Inflammation / autoimmune ──────────────────────────────────
            when 'C-reactive protein (CRP)'                                then 'crp'
            when 'VSH'                                                     then 'esr'  -- Romanian: Viteza de Sedimentare a Hematiilor = ESR
            when 'Se CA 125 level'                                         then 'ca125'
            when 'Tissue transglutaminase IgA level'                       then 'ttg_iga'
            when 'Tissu transglutaminase IgA lev'                          then 'ttg_iga'  -- legacy source typo

            -- ── Other biochemistry ─────────────────────────────────────────
            when 'CK (serum creatine kinase)'                              then 'ck_total'
            when 'Blood group OAB'                                         then 'blood_group'
            when 'Rh factor'                                               then 'rh_factor'

            -- ── Microbiology / infection screen ───────────────────────────
            when 'Campylobacter (faeces culture)'                          then 'campylobacter_faeces_culture'
            when 'Campylobacter NOT isolated (faeces culture)'             then 'campylobacter_faeces_culture'  -- legacy name
            when 'Clos. difficile PCR'                                     then 'c_diff_pcr'
            when 'Clos. difficile toxin A/B'                               then 'c_diff_toxin_a_b'
            when 'E.coli O157 (faeces culture)'                            then 'e_coli_faeces_culture'
            when 'Salmonella (faeces culture)'                             then 'salmonella_faeces_culture'
            when 'Shigella (faeces culture)'                               then 'shigella_faeces_culture'
            when 'Cryptosporidium (cumulative)'                            then 'cryptosporidium_cumulative'
            when 'Cryptosporidium (OCP PCR)'                               then 'cryptosporidium_ocp_pcr'
            when 'Giardia (cumulative)'                                    then 'giardia_cumulative'
            when 'Giardia (OCP PCR)'                                       then 'giardia_ocp_pcr'
            when 'Quantity faecal immunochemical test'                     then 'fit_quantitative'
            when 'STAIN'                                                   then 'stain'
            when 'MRSA screen'                                             then 'mrsa'
            when 'HBsAg (screening)'                                       then 'hbsag'
            when 'Hepatitis B Surface Antigen (final interpretation)'      then 'hepatitis_b'
            when 'Hepatitis C Antibody (final interpretation)'             then 'hepatitis_c'
            when 'HIV screen  (final interpretation)'                      then 'hiv'

            -- ── Fallback ──────────────────────────────────────────────────
            -- Auto-generates a slug for any analyte not explicitly mapped.
            -- New analytes surface in stg_unknown_values via the ingestion
            -- pipeline and should be added above once reviewed.
            else trim(
                lower(regexp_replace(p.analyte_name, '[^a-zA-Z0-9]+', '_', 'g')),
                '_'
            )

        end as analyte_slug

    from parsed p

),

deduped as (

    -- Deduplicate to the latest ingested version of each logical blood test row.
    --
    -- Logical key: (test_date, analyte_slug, collection_site)
    -- A blood test is uniquely identified by what was measured (analyte_slug),
    -- when it was taken (test_date), and which lab took it (collection_site).
    --
    -- When a source row is edited in Google Sheets and re-ingested, the new
    -- version has a later loaded_at and a different source_row_hash.
    -- row_number() = 1 selects the most recently ingested version only.
    --
    -- Rows with a NULL test_date (unparseable date string) are retained here —
    -- they will fail the not_null dbt test and surface for investigation.

    select
        *,
        row_number() over (
            partition by test_date, analyte_slug, collection_site
            order by loaded_at desc, id desc
        ) as _row_number

    from slugged

)

-- ── Final output ──────────────────────────────────────────────────────────────
-- Deduplicated rows only (_row_number = 1).
-- _row_number is an internal dedup column; excluded from the view output.
-- Column order follows database-schema.md silver layer definition.

select
    id,
    test_date,
    test_type,
    analyte_name,
    analyte_slug,
    result_qualifier,
    result_numeric,
    result_is_numeric,
    result_text,
    unit,
    unit_normalised,      -- null placeholder; populated in int_blood_tests_normalised_vw
    result_normalised,    -- null placeholder; populated in int_blood_tests_normalised_vw
    ref_type,
    ref_low,
    ref_high,
    ref_text_raw,
    collection_site,
    notes,
    false                 as is_duplicate,
    source_row_hash,
    loaded_at

from deduped
where _row_number = 1
