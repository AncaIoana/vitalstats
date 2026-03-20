# Medications & Vaccines Source Schema
### vitalStats — Source Documentation

---

## Source

- **Type:** Google Sheets (manual entry)
- **Sheet name:** Vaccine and Medication Tracker
- **Tabs:** `Medications` (primary), `Vaccines` (secondary)
- **Access:** Google Sheets API v4 via service account (same pattern as blood tests)
- **Sheet ID:** separate from blood tests sheet — store in env var `MEDICATIONS_SHEET_ID`
- **Update frequency:** Manual — new rows added when medication changes or vaccines administered
- **Ingestion method:** Hash-based deduplication (ADR-005)

---

## Tab 1: `Medications`

### Raw Column Definitions

| Column | Raw name | Type in source | Notes |
|---|---|---|---|
| Medication Name | `Medication Name` | String | See normalisation below |
| Dosage | `Dosage` | String | `"250mg"`, `"1500mg/400unit"` |
| Start Date | `Start Date` | Date / String | Excel datetime or string — see below |
| End Date | `End Date` | Date / NULL | NULL = ongoing |
| Frequency | `Frequency (times/day)` | Numeric | 0 = paused/stopped; 0.5 = alternate days |
| Notes | `Notes` | String | Free text |

### Date Format

Most dates are Excel datetime objects. One known bad date exists:

| Raw value | Issue | Correct value |
|---|---|---|
| `"15-Feb-0204"` | Year typo — should be 2024 | `2024-02-15` |

**Parser:**
```python
from datetime import datetime, date

def parse_medication_date(raw) -> date | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, str):
        raw = raw.strip()
        # Known bad date fix
        if raw == "15-Feb-0204":
            return date(2024, 2, 15)
        for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
    raise ValueError(f"Cannot parse medication date: '{raw}'")
```

### Observed Medications

| Raw name | Canonical slug | Notes |
|---|---|---|
| `Centrum advance` | `centrum_advance` | Multivitamin |
| `Evacal D3` | `evacal_d3` | Calcium + Vitamin D |
| `Ferrous sulfade` | `ferrous_sulfate` | Typo in source — normalise on ingest |
| `Lansoprazole-orodispersible` | `lansoprazole` | PPI |
| `Metyrapone` | `metyrapone` | Cushing's treatment — clinically significant |
| `Omeprazole` | `omeprazole` | PPI |
| `Simvastatin` | `simvastatin` | Statin |

### Frequency Column — Parsing Rules

| Value | Meaning | `is_active` |
|---|---|---|
| `> 0` (e.g. 1.0, 2.0, 0.5) | Active, taken N times per day | TRUE |
| `0` | Paused or stopped | FALSE |
| NULL | Unknown / not recorded | NULL |

Note: `0.5` means alternating between 1 per day and 0 per day — noted in source notes.

### Known Data Quality Issues

| Issue | Example | Handling |
|---|---|---|
| Typo in medication name | `"Ferrous sulfade"` (should be sulfate) | Normalise to slug `ferrous_sulfate` on ingest |
| Bad year in date | `"15-Feb-0204"` | Hardcode correction to `2024-02-15` in parser |
| Overlapping date ranges | Ferrous sulfate has overlapping periods | Hash dedup catches exact duplicates; overlaps stored as-is, reviewed manually |
| Frequency = 0 rows | Metyrapone paused for surgery | Store as-is; `is_active = FALSE` |

---

## Tab 2: `Vaccines`

### Raw Column Definitions

| Column | Raw name | Type in source | Notes |
|---|---|---|---|
| Person | `Name` | String | `"Anca"` or `"Lukasz"` — **filter to Anca only** |
| Date Given | `Date Given` | Excel datetime | Consistent format |
| Vaccine | `Vaccine Name & Dose` | String | Trailing spaces common — strip on ingest |
| Immunity Duration | `Immunity Duration (Years)` | String | Free text — `"1 year"`, `"Lifelong"`, `"Part of 3-dose course"` |
| Booster Due | `Booster Due` | Mixed | Year integer (2028.0), NULL, or string — see below |
| Notes | `Notes` | String | Free text |

### Critical Filtering Rule

**Only rows where `Name = 'Anca'` are ingested. Lukasz rows are discarded at the Python ingestion stage before loading into Silver.**

```python
vaccines_df = vaccines_df[vaccines_df['Name'].str.strip() == 'Anca']
```

### Booster Due Column — Parsing Rules

| Raw value | Type | Handling |
|---|---|---|
| `2028.0` | Float year | `booster_due_year = 2028`, `booster_due_date = 2028-01-01` |
| `2026.0` | Float year | `booster_due_year = 2026`, `booster_due_date = 2026-01-01` |
| `None` | NULL | Both NULL |
| `"See 3rd dose date"` | String | Both NULL; copy to notes |
| `"Check booster guidance"` | String | Both NULL; copy to notes |

```python
def parse_booster_due(raw):
    if raw is None:
        return None, None
    if isinstance(raw, (int, float)):
        year = int(raw)
        return year, date(year, 1, 1)
    return None, None  # string values → store in notes instead
```

### Observed Vaccines (Anca only)

| Raw vaccine name | Canonical slug |
|---|---|
| `Flu (Influenza)` | `flu_influenza` |
| `Covid-19 ` (trailing space) | `covid_19` |
| `Covid-19` | `covid_19` |
| `DTP (Diptheria, Tetanus & Polio Combined)` | `dtp` |
| `Typhoid` | `typhoid` |
| `Hepatitis A (Hep A)` | `hepatitis_a` |
| `HPV (1st dose)` | `hpv` |
| `HPV (2nd dose)` | `hpv` |
| `HPV (3rd dose)` | `hpv` |

### Known Data Quality Issues

| Issue | Example | Handling |
|---|---|---|
| Trailing spaces in vaccine names | `"Covid-19 "` | Strip whitespace on ingest |
| Inconsistent Covid name | `"Covid-19 "` vs `"Covid-19"` | Both normalise to slug `covid_19` |
| Multi-dose vaccines | HPV appears as 1st/2nd/3rd dose | All map to same `vaccine_slug = "hpv"` |
| Old records with superseded boosters | Typhoid 2016 with `"there is a more recent record"` | Ingest all; latest record takes precedence in Gold mart |
| Booster due as string | `"See 3rd dose date"` | Parse to NULL; log in notes field |

---

## Cross-source ML potential

Medication data is particularly valuable for enriching blood test analysis:

- **Metyrapone vs cortisol/ALT:** Metyrapone is a cortisol synthesis inhibitor. ALT has been persistently elevated — correlating ALT with Metyrapone dose and active periods could be clinically significant.
- **Ferrous sulfate vs ferritin:** Direct relationship — ferritin levels should respond to iron supplementation. Visualising ferritin trend against iron supplement dose is a key insight.
- **Simvastatin vs cholesterol:** Direct relationship — cholesterol markers should correlate with statin use.
- **Omeprazole/Lansoprazole periods:** PPI use may affect absorption of other medications; worth flagging in ML features.
- **Medication active flag as ML feature:** `med_metyrapone_active` becomes a binary feature in every blood test model — blood results should be interpreted differently depending on whether Metyrapone was active at the time.

---

## Parser Validation Notifications

All parsers emit structured warnings for field values that are technically valid but suspicious. Non-blocking — row still ingested — but logged to `silver.stg_unknown_values`. See ADR-017.

**Triggers for medications:**
- Date parses but year < 2000 or year > current year + 1
- `frequency_per_day` > 10 (likely data entry error)
- End date before start date
- Medication name fuzzy-matches a known slug but is not an exact match

**Triggers for vaccines:**
- Date given in the future
- Booster due year more than 30 years in the future
- Vaccine name not in the known vaccines registry

**Note:** The `"15-Feb-0204"` date has been corrected in the source sheet. The parser hardcode can be removed once confirmed. The year plausibility rule would have caught this automatically.

**Implementation note:** Deferred to Phase 1b. Phase 1 uses hard/soft failure model only.

---

## Ingestion Script Specification

**File:** `ingestion/google_sheets/extract_medications.py`

**Inputs:**
- Google Sheets API credentials (same service account as blood tests)
- Sheet ID (env var `MEDICATIONS_SHEET_ID`)
- Tab names: `Medications`, `Vaccines`

**Outputs:**
- Raw JSON to `s3://vitalstats-raw/medications_vaccines/YYYY-MM-DD/medications.json`
- Raw JSON to `s3://vitalstats-raw/medications_vaccines/YYYY-MM-DD/vaccines.json`
- Loaded into `silver.stg_medications` and `silver.stg_vaccines`

**Validation checks (pre-load):**
1. Expected columns present in both tabs (raise if missing)
2. At least one row with `Name = 'Anca'` in Vaccines tab
3. All Start Dates parseable (log bad dates, don't crash — apply known corrections first)
4. Row count >= previous run (alert if rows disappear)
