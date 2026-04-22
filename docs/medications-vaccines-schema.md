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

Most dates are Excel datetime objects. Parser handles both Excel datetime objects and string formats.

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
| `Evacal D3` | `evacal_d3` | Calcium + Vitamin D supplement |
| `Ferrous Sulfate` | `ferrous_sulfate` | Iron supplement |
| `Lansoprazole-orodispersible` | `lansoprazole` | PPI |
| `Metyrapone` | `metyrapone` | Clinically significant — monitor relevant markers |
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
| Overlapping date ranges | Ferrous sulfate has overlapping periods | Hash dedup catches exact duplicates; overlaps stored as-is, reviewed manually |
| Frequency = 0 rows | Medication paused temporarily | Store as-is; `is_active = FALSE` |

---

## Tab 2: `Vaccines`

### Raw Column Definitions

| Column | Raw name | Type in source | Notes |
|---|---|---|---|
| Person | `Name` | String | Two people in sheet — **filter to tracked person only** |
| Date Administered | `Date Administered` | Excel datetime | Consistent format |
| Vaccine Type & Dose | `Vaccine Type & Dose` | String | Strip whitespace on ingest. Type + dose info e.g. "HPV (1st dose)", "Covid-19" |
| Immunity Duration | `Immunity Duration (Years)` | String | Free text — `"1 year"`, `"Long-term (10+ years, possibly lifelong)"`, `"Part of 3-dose course"` |
| Booster Due | `Booster Due` | Mixed | Year integer (2028.0), NULL, or string — see below |
| Is Most Recent | `Is this the most recent record?` | String | `"Yes"` / `"No"` — parsed to boolean. See below |
| Administration Site | `Administration site` | String | Free text — `"Intramuscular (IM) - right deltoid"`. Nullable (sparse on older records) |
| Vaccination Location | `Vaccination location` | String | Free text — `"Boots, Manchester"`, `"NHS - Manchester Sportcity Vaccination Centre"`. Nullable |
| Batch & Lot Number | `Batch and lot number` | String | Free text — `"AHBVD221AB"`. Nullable |
| Vaccine Name | `Vaccine Name` | String | Product name — `"Engerix B 20 mcg p/f syringe (Hepatitis B)"`, `"VAQTA Adult"`. Free text, nullable. Distinct from Vaccine Type & Dose |
| Expiration Date | `Expiration date` | String | Month-year format — `"Dec-2027"`. Parsed to DATE as YYYY-MM-01. Nullable |
| Manufacturer | `Manufacturer` | String | Free text — `"GSK"`. Nullable |
| Notes | `Notes` | String | Free text |

### Critical Filtering Rule

**Only rows belonging to the tracked person are ingested. Partner rows are discarded at the Python ingestion stage before loading into Silver.**

```python
vaccines_df = vaccines_df[vaccines_df["Name"].str.strip() == TRACKED_PERSON_NAME]
```

`TRACKED_PERSON_NAME` is loaded from an environment variable — never hardcoded in the script.

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
    return None, None  # string values -> store in notes instead
```

### Is Most Recent Column — Parsing Rules

Ingested as a boolean (`is_most_recent`). Used in Gold to filter the "current" vaccine status per vaccine type.

| Raw value | Parsed |
|---|---|
| `"Yes"` | `TRUE` |
| `"No"` | `FALSE` |
| NULL / empty | `FALSE` |

> **Future enhancement:** When a new record appears for a vaccine type that already has `is_most_recent = TRUE`, trigger a notification or automation to flag that the source sheet may need updating. Deferred — not in Phase 1b scope.

### Expiration Date Column — Parsing Rules

Source format is month-year only (e.g. `"Dec-2027"`). Parsed to a `DATE` using the 1st of the month as convention.

```python
from datetime import datetime, date

def parse_expiration_date(raw) -> date | None:
    if raw is None or str(raw).strip() == "":
        return None
    raw = str(raw).strip()
    for fmt in ("%b-%Y", "%B-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()  # e.g. 2027-12-01
        except ValueError:
            continue
    return None  # unparseable — log warning, store NULL
```

### Observed Vaccines (tracked person only)

| Raw vaccine type & dose | Canonical slug | Notes |
|---|---|---|
| `Flu (Influenza)` | `flu_influenza` | Annual |
| `Covid-19` | `covid_19` | |
| `DTP (Diptheria, Tetanus & Polio Combined)` | `dtp` | |
| `Typhoid` | `typhoid` | |
| `Hepatitis A` | `hepatitis_a` | Multi-dose course |
| `Hepatitis B (1st dose)` | `hepatitis_b` | Multi-dose course (3 doses) |
| `HPV (1st dose)` | `hpv` | Multi-dose course (3 doses) |
| `HPV (2nd dose)` | `hpv` | |
| `HPV (3rd dose)` | `hpv` | |

### Known Data Quality Issues

| Issue | Example | Handling |
|---|---|---|
| Multi-dose vaccines | HPV appears as 1st/2nd/3rd dose; Hepatitis B as 1st/2nd/3rd dose | All map to same `vaccine_slug` (e.g. `"hpv"`, `"hepatitis_b"`) |
| Older records sparse on new columns | Pre-2022 records have no location, batch, manufacturer | All new columns are nullable — ingest as-is |
| `is_most_recent` may go stale | If sheet isn't updated when new vaccine given | Ingest as-is; Gold mart can cross-check with `max(date_administered)` per slug as validation |
| Booster due as string | `"See 3rd dose date"`, `"Check booster guidance"` | Parse to NULL; log in notes field |
| Expiration date month-year only | `"Dec-2027"` | Parse to `YYYY-MM-01` convention |
| Notes contain multi-dose schedule | `"Dose 2: 8 May 2026, Dose 3: 8 Oct 2026"` | Store as free text; no structured parsing needed |
| Hepatitis A name change | Old records say `"Hepatitis A (Hep A)"`, newer say `"Hepatitis A"` | Both map to `hepatitis_a` |

---

## Cross-source ML potential

Medication data is particularly valuable for enriching blood test analysis:

- **Clinically significant medication vs relevant markers:** Correlating active periods and dosage changes with corresponding lab markers can surface clinically meaningful trends worth discussing with a specialist.
- **Ferrous sulfate vs ferritin:** Direct relationship — ferritin levels should respond to iron supplementation. Visualising ferritin trend against iron supplement dose is a key insight.
- **Simvastatin vs cholesterol:** Direct relationship — cholesterol markers should correlate with statin use.
- **Omeprazole/Lansoprazole periods:** PPI use may affect absorption of other medications; worth flagging in ML features.
- **Medication active flag as ML feature:** `med_<slug>_active` becomes a binary feature in every blood test model — blood results should be interpreted differently depending on what was active at the time.

---

## Parser Validation Notifications

All parsers emit structured warnings for field values that are technically valid but suspicious. Non-blocking — row still ingested — but logged to `silver.stg_unknown_values`. See ADR-017.

**Triggers for medications:**
- Date parses but year < 2000 or year > current year + 1
- `frequency_per_day` > 10 (likely data entry error)
- End date before start date
- Medication name fuzzy-matches a known slug but is not an exact match

**Triggers for vaccines:**
- Date administered in the future
- Booster due year more than 30 years in the future
- Vaccine name not in the known vaccines registry

**Implementation note:** Deferred to Phase 1b. Phase 1 uses hard/soft failure model only.

---

## Ingestion Script Specification

**File:** `ingestion/google_sheets/extract_medications.py`

**Inputs:**
- Google Sheets API credentials (same service account as blood tests)
- Sheet ID (env var `MEDICATIONS_SHEET_ID`)
- Tracked person name (env var `TRACKED_PERSON_NAME`)
- Tab names: `Medications`, `Vaccines`

**Outputs:**
- Raw JSON to `s3://vitalstats-raw/medications_vaccines/YYYY-MM-DD/medications.json`
- Raw JSON to `s3://vitalstats-raw/medications_vaccines/YYYY-MM-DD/vaccines.json`
- Loaded into `silver.stg_medications` and `silver.stg_vaccines`

**Validation checks (pre-load):**
1. Expected columns present in both tabs (raise if missing)
2. At least one row for the tracked person in Vaccines tab
3. All Start Dates parseable (log bad dates, don't crash)
4. Row count >= previous run (alert if rows disappear)
