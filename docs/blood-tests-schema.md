# Blood Tests Source Schema
### vitalStats — Source Documentation

---

## Source

- **Type:** Google Sheets (manual entry)
- **Sheet name:** Blood tests
- **Tab:** `blood_tests_bulk` (primary), `menoscale` (secondary)
- **Access:** Google Sheets API v4 via service account
- **Update frequency:** Manual — new rows added after each test; occasional corrections to past rows
- **Ingestion method:** Hash-based deduplication (see ADR-005)

---

## Tab 1: `blood_tests_bulk`

### Raw Column Definitions

| Column | Raw name | Type in source | Notes |
|---|---|---|---|
| Date | `Date` | String | Format: `"6-Apr-2023"` (day-MonthAbbrev-year) |
| Test Type | `Test Type` | String | Category of test |
| Analyte | `Analyte` | String | Name of the specific marker measured |
| Result | `Result` | String | Numeric or text — see below |
| Unit | `Unit` | String | Often inconsistent across labs |
| Reference Interval | `Reference Interval` | String | Highly variable format — see below |
| Collection | `Collection` | String | Lab / practice name |
| Notes | `Notes ` | String | Trailing space in header — strip on ingest |

---

### Date Format

All dates are in the format `D-Mon-YYYY` where Mon is a 3-letter English month abbreviation.

```
"6-Apr-2023"   → 2023-04-06
"27-Feb-2023"  → 2023-02-27
"18-Dec-2025"  → 2025-12-18
```

**Parser:** `datetime.strptime(value, "%d-%b-%Y")`

---

### Test Types (observed values)

| Value | Description |
|---|---|
| `Biochemistry` | Metabolic panel, liver, kidney, lipids, hormones |
| `Hematology` | Blood cell counts, iron studies, coagulation |
| `Immunochemistry` | Antibodies, immunological markers |
| `Microbiology` | Cultures, PCR, pathogen detection |
| `Quantitv faecal immunochem tst` | Faecal immunochemical test (FIT) — typo in source, normalise |
| `Quantity faecal immunochem tst` | Same test, different spelling — deduplicate to single value |

**Normalised slug:** `biochemistry`, `hematology`, `immunochemistry`, `microbiology`, `fit_test`

---

### Result Column — Parsing Rules

The `Result` column is a string that can contain:

| Pattern | Example | Handling |
|---|---|---|
| Plain numeric | `"46"`, `"2.45"`, `"337"` | Cast to `NUMERIC` directly |
| Less-than with value | `"< 0.6"`, `"<35"` | `result_numeric = 0.6`, `result_qualifier = "lt"` |
| Greater-than with value | `">120"` | `result_numeric = 120`, `result_qualifier = "gt"` |
| Categorical negative | `"negative"`, `"Negative"` | `result_is_numeric = FALSE`, `result_text = "negative"` |
| Categorical positive | `"positive"`, `"Positive"` | `result_is_numeric = FALSE`, `result_text = "positive"` |
| Not detected | `"Not Detected"` | `result_is_numeric = FALSE`, `result_text = "not_detected"` |
| Unformed (stool) | `"Unformed"` | `result_is_numeric = FALSE`, `result_text = "unformed"` |
| Free text | `"Discussed with patient"` | `result_is_numeric = FALSE`, `result_text = raw value` |

**Python parsing function** (to be implemented in `ingestion/utils/result_parser.py`):
```python
import re

def parse_result(raw: str) -> dict:
    raw = raw.strip()
    # Less-than
    m = re.match(r'^[<＜]\s*(\d+\.?\d*)$', raw)
    if m:
        return {"numeric": float(m.group(1)), "qualifier": "lt", "is_numeric": True}
    # Greater-than
    m = re.match(r'^[>＞]\s*(\d+\.?\d*)$', raw)
    if m:
        return {"numeric": float(m.group(1)), "qualifier": "gt", "is_numeric": True}
    # Plain numeric
    try:
        return {"numeric": float(raw), "qualifier": None, "is_numeric": True}
    except ValueError:
        return {"numeric": None, "qualifier": None, "is_numeric": False, "text": raw.lower()}
```

---

### Reference Interval — Parsing Rules

Highly inconsistent. Applied in dbt staging model.

| Pattern | Example | `ref_low` | `ref_high` | `ref_type` |
|---|---|---|---|---|
| Range | `"35-50"` | 35 | 50 | `range` |
| Range with spaces | `"2.20 - 2.60"` | 2.20 | 2.60 | `range` |
| Less-than | `"<35"`, `"< 20"` | NULL | 35 | `lt` |
| Greater-than | `">1.99 %"` | 1.99 | NULL | `gt` |
| N/A | `"N/A"` | NULL | NULL | `categorical` |
| Free text / complex | `"0 (no AKI) to 3 (severe AKI)"` | NULL | NULL | `narrative` |
| Adults pattern | `"Adults: <1.2"` | NULL | 1.2 | `lt` |
| Empty | `""` | NULL | NULL | `unknown` |

---

### Collection Sites (observed values)

| Raw value | Normalised | Country | Type |
|---|---|---|---|
| `New Islington Medical Practice` | `new_islington_gp` | UK | NHS GP |
| `Salford Royal` | `salford_royal` | UK | NHS Hospital |
| `Nuffield Health` | `nuffield_health` | UK | Private |
| `Synevo` | `synevo` | Romania | Private lab |

---

### Unit Inconsistencies — Key Analytes

These analytes appear in multiple units across labs and **must be normalised**:

| Analyte | Synevo unit | NHS unit | Conversion to NHS | Notes |
|---|---|---|---|---|
| All cholesterol markers | `mg/dL` | `mmol/L` | `mg/dL ÷ 38.67` | Total, HDL, LDL, non-HDL |
| Glucose | `mg/dL` | `mmol/L` | `mg/dL ÷ 18.02` | |
| Calcium (serum) | `mg/dL` | `mmol/L` | `mg/dL ÷ 4.008` | |
| Bilirubin | `mg/dL` | `μmol/L` | `mg/dL × 17.1` | |
| HbA1c | `%` (NGSP) | `mmol/mol` (IFCC) | `(% − 2.152) ÷ 0.09148` | Critical — very different numbers |
| WBC / RBC counts | `K/µL` or `M/µL` | `10*9/L` or `10*12/L` | `K/µL = 10*9/L` (same magnitude) | Unit names differ, values are equivalent |
| Ferritin | `ng/mL` | `μg/L` | `1:1` (numerically identical) | Different names, same value |

---

### Known Data Quality Issues

| Issue | Example | Handling |
|---|---|---|
| Duplicate rows | Alkaline phosphatase on 22-Sep-2023 appears twice | Hash-based dedup in ingestion |
| Trailing space in `Notes ` header | `"Notes "` | Strip on ingest |
| Mixed language in notes | Romanian text in Synevo notes | Store as-is; no translation needed |
| Inconsistent analyte naming | `"Bilirubin (serum)"` vs `"Bilirubin total"` | Map to canonical `analyte_slug` |
| Multi-line reference intervals | Cholesterol HDL reference interval spans 4 lines | Flatten to single string on ingest |
| Non-standard values | `"0 (no AKI) to 3 (severe AKI)"` | Parse as narrative; use canonical ranges |
| Empty units | Some Salford Royal rows have no unit | Infer from analyte + canonical range table |

---

### Analyte Slug Mapping (partial — key analytes)

Generated via: `lower(regexp_replace(analyte_name, '[^a-zA-Z0-9]+', '_', 'g'))`

| Raw analyte name | Canonical slug |
|---|---|
| `ALT (Alanine aminotransferase)` | `alt` |
| `AST (Aspartate aminotransferase)` | `ast` |
| `Albumin (serum)` | `albumin` |
| `Alkaline phosphatase (serum)` | `alkaline_phosphatase` |
| `Bilirubin (serum)` | `bilirubin` |
| `Bilirubin total` | `bilirubin` ← maps to same slug |
| `Cholesterol HDL (serum)` | `cholesterol_hdl` |
| `Cholesterol (non-HDL)` | `cholesterol_non_hdl` |
| `Cholesterol (serum) / HDL ratio` | `cholesterol_hdl_ratio` |
| `Ferritin (serum)` | `ferritin` |
| `Glucose (fasting)` | `glucose_fasting` |
| `HbA1c` | `hba1c` |
| `Haemoglobin` | `haemoglobin` |
| `TSH` | `tsh` |
| `Vitamin D` | `vitamin_d` |
| `White blood cell count WBC` | `wbc` |
| `Red blood cell (RBC) count` | `rbc` |
| `Platelet count` | `platelets` |

---

## Tab 2: `menoscale`

The MenoScale is a validated questionnaire from Zoe measuring menopause symptom burden. Score is 0–100, higher = greater symptom burden. Reference: [MenoScale Calculator](https://zoe.com/learn/menoscale-calculator-menopause-research).

### Confirmed structure

| Column | Raw name | Type | Notes |
|---|---|---|---|
| Date | `Date` | String → DATE | **Inconsistent format — see below** |
| Score | `Score (out of 100)` | Integer | 0–100; higher = more symptoms |

### Current data (2 readings)

| Date | Score |
|---|---|
| 6-Sep-2024 | 11 |
| 16-Apr-2025 | 17 |

Trend: **increasing** (+6 over ~7 months). Will become more meaningful as readings accumulate.

### Date Format — Known Inconsistency

The menoscale tab uses **two different date formats** (unlike `blood_tests_bulk` which is consistent):

| Format | Example | Parser |
|---|---|---|
| Hyphen-separated | `"6-Sep-2024"` | `datetime.strptime(value, "%d-%b-%Y")` |
| Space-separated | `"16 Apr 2025"` | `datetime.strptime(value, "%d %b %Y")` |

**Handling:** The ingestion script must try both formats with a fallback:

```python
def parse_menoscale_date(raw: str) -> date:
    raw = raw.strip()
    for fmt in ("%d-%b-%Y", "%d %b %Y", "%d-%B-%Y", "%d %B %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse menoscale date: '{raw}'")
```

This also handles full month names (`"April"`) in case future entries use those.

### Staging model: `silver.stg_menoscale`

```sql
CREATE TABLE silver.stg_menoscale (
    stg_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recorded_date    DATE NOT NULL,
    score            INTEGER NOT NULL CHECK (score >= 0 AND score <= 100),
    source_row_hash  TEXT NOT NULL,
    loaded_at        TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### dbt tests
- `not_null` on `recorded_date`, `score`
- `unique` on `recorded_date`
- `accepted_range` custom test: `score between 0 and 100`

### Mart output
Included in `gold.mart_health_timeline` with:
- `event_type = 'menoscale'`
- `metric_name = 'menoscale_score'`
- `metric_value_numeric = score`

### Cross-source ML potential (Phase 3+)
Once more readings exist and Fitbit data is added:
- Correlate score with ferritin levels (low iron is a known menopause symptom driver)
- Correlate with sleep quality from Fitbit
- Correlate with liver markers (ALT has been persistently elevated — worth monitoring alongside hormonal changes)

---

## Parser Validation Notifications

All parsers emit structured warnings for field values that are technically valid but suspicious. Warnings are non-blocking — the row is still ingested — but are logged to `silver.stg_unknown_values` and included in `pipeline_run_log.rows_skipped_detail`. See ADR-017.

**Triggers for blood tests:**
- Result numeric > 10x the reference range high for that analyte
- Date parses but year < 2000 or year > current year + 1
- Unit not in the canonical unit list for that analyte
- Reference interval format matches no known pattern
- Analyte name fuzzy-matches a known slug but is not an exact match

**Implementation note:** Deferred to Phase 1b. Phase 1 uses hard/soft failure model only.

---

## Known Values Registry

Maintained in `ingestion/config/known_values.py`. This is the canonical list of expected values for key fields. Any value arriving from the source that is not in this registry triggers detection logic (see ADR-014).

### Expected test types

| Raw value | Normalised slug | Action if new value arrives |
|---|---|---|
| `Biochemistry` | `biochemistry` | Hard failure — unknown test type |
| `Hematology` | `hematology` | Hard failure — unknown test type |
| `Immunochemistry` | `immunochemistry` | Hard failure — unknown test type |
| `Microbiology` | `microbiology` | Hard failure — unknown test type |
| `Quantitv faecal immunochem tst` | `fit_test` | Hard failure — unknown test type |
| `Quantity faecal immunochem tst` | `fit_test` | Hard failure — unknown test type |

### Expected collection sites

| Raw value | Normalised slug | Country | Unit convention | Action if new value arrives |
|---|---|---|---|---|
| `New Islington Medical Practice` | `new_islington_gp` | UK | NHS (mmol/L) | Partial run + warning |
| `Salford Royal` | `salford_royal` | UK | NHS (mmol/L) | Partial run + warning |
| `Nuffield Health` | `nuffield_health` | UK | NHS (mmol/L) | Partial run + warning |
| `Synevo` | `synevo` | Romania | mg/dL → convert | Partial run + warning |

### What happens when an unknown value is detected

1. The row is ingested into `raw.blood_tests_raw` (never discard raw data)
2. A record is written to `silver.stg_unknown_values` with the raw value and an example row
3. For unknown collection sites: `pipeline_run_log.status` is set to `"partial"`
4. For unknown analytes: pipeline continues with `status = "success"`; analyte will lack reference range in Gold until manually added
5. Resolution: update `known_values.py`, add to `gold.mart_reference_ranges` if needed
6. For new analytes: run `dbt run`
7. For new collection sites: run `dbt run --full-refresh --select stg_blood_tests`, then `dbt run` for marts
8. Set `stg_unknown_values.resolved = TRUE`, `resolved_at = NOW()`, add `resolution_note`

---

## Ingestion Script Specification

**File:** `ingestion/google_sheets/extract.py`

**Inputs:**
- Google Sheets API credentials (service account JSON, via env var `GOOGLE_SHEETS_CREDENTIALS`)
- Sheet ID (env var `BLOOD_TESTS_SHEET_ID`)
- Tab name (default: `blood_tests_bulk`)

**Outputs:**
- Raw JSON to `s3://vitalStats-raw/blood_tests/YYYY-MM-DD/blood_tests_bulk.json`
- Loaded into `raw.blood_tests_raw` (deduped by row hash)
- Updated `raw.pipeline_state` record

**Validation checks (pre-load):**
1. Expected columns present (raise if missing)
2. Date column parseable for all rows (log failures, don't crash)
3. At least 1 numeric result exists in the result column
4. Row count >= previous run row count (alert if rows disappear)
