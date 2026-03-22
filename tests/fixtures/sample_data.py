"""
Synthetic fixture data for vitalStats ingestion tests.

All data is entirely fictional. Names, dates, values, and lab names are
invented for testing purposes only (and themed accordingly).

Collection sites used:
- "St Mary Mead Clinic"           NHS GP (Miss Marple's village)
- "Styles Court Hospital"         NHS Hospital (The Mysterious Affair at Styles)
- "Nuffield Andover"              Private (fictional branch)
- "Orient Express Diagnostics"    Romanian private lab, mg/dL units (fictional)
- "The Mousetrap Medical Centre"  Unknown site, for unknown-value detection tests

Person names used:
- "Poirot"   — the tracked person (kept by name filter)
- "Hastings" — filtered out at ingestion

Covers:
- blood_tests_bulk: numeric, qualifier (</>), categorical, free text results
- menoscale: both date formats (hyphen and space)
- medications: normal, frequency=0, ongoing, alternate-days
- vaccines: Poirot and Hastings rows (to exercise the name filter)
"""

# ---------------------------------------------------------------------------
# Blood tests — blood_tests_bulk tab
# ---------------------------------------------------------------------------
# Mirrors the raw dict structure returned by the Google Sheets API v4.
# Column names match the real sheet exactly.

BLOOD_TEST_ROWS = [
    # --- Plain numeric result, NHS site ---
    {
        "Date": "6-Apr-2023",
        "Test Type": "Biochemistry",
        "Analyte": "ALT (Alanine aminotransferase)",
        "Result": "32",
        "Unit": "U/L",
        "Reference Interval": "7-56",
        "Collection": "St Mary Mead Clinic",
        "Notes": "",
    },
    # --- Less-than qualifier ---
    {
        "Date": "6-Apr-2023",
        "Test Type": "Biochemistry",
        "Analyte": "TSH",
        "Result": "< 0.6",
        "Unit": "mIU/L",
        "Reference Interval": "0.27-4.2",
        "Collection": "St Mary Mead Clinic",
        "Notes": "",
    },
    # --- Greater-than qualifier ---
    {
        "Date": "6-Apr-2023",
        "Test Type": "Hematology",
        "Analyte": "Ferritin (serum)",
        "Result": ">120",
        "Unit": "μg/L",
        "Reference Interval": "13-150",
        "Collection": "St Mary Mead Clinic",
        "Notes": "Sample haemolysed",
    },
    # --- Categorical: negative ---
    {
        "Date": "15-Jun-2023",
        "Test Type": "Microbiology",
        "Analyte": "H. pylori antigen",
        "Result": "Negative",
        "Unit": "",
        "Reference Interval": "N/A",
        "Collection": "Styles Court Hospital",
        "Notes": "",
    },
    # --- Categorical: not detected ---
    {
        "Date": "15-Jun-2023",
        "Test Type": "Microbiology",
        "Analyte": "Hepatitis B surface antigen",
        "Result": "Not Detected",
        "Unit": "",
        "Reference Interval": "N/A",
        "Collection": "Styles Court Hospital",
        "Notes": "",
    },
    # --- Free text result ---
    {
        "Date": "15-Jun-2023",
        "Test Type": "Biochemistry",
        "Analyte": "AKI Risk Score",
        "Result": "Discussed with patient",
        "Unit": "",
        "Reference Interval": "0 (no AKI) to 3 (severe AKI)",
        "Collection": "Styles Court Hospital",
        "Notes": "",
    },
    # --- Conversion: mg/dL units requiring conversion to mmol/L ---
    {
        "Date": "10-Jan-2024",
        "Test Type": "Biochemistry",
        "Analyte": "Cholesterol (serum)",
        "Result": "185",
        "Unit": "mg/dL",
        "Reference Interval": "< 200",
        "Collection": "Orient Express Diagnostics",
        "Notes": "",
    },
    # --- Conversion: HbA1c in % (NGSP) — requires IFCC conversion to mmol/mol ---
    # NGSP 5.4% → IFCC = (5.4 - 2.152) / 0.09148 ≈ 35.5 mmol/mol
    {
        "Date": "10-Jan-2024",
        "Test Type": "Biochemistry",
        "Analyte": "HbA1c",
        "Result": "5.4",
        "Unit": "%",
        "Reference Interval": "< 6.5",
        "Collection": "Orient Express Diagnostics",
        "Notes": "",
    },
    # --- Reference interval: Adults: pattern ---
    {
        "Date": "10-Jan-2024",
        "Test Type": "Biochemistry",
        "Analyte": "Bilirubin (serum)",
        "Result": "14",
        "Unit": "mg/dL",
        "Reference Interval": "Adults: < 1.2",
        "Collection": "Orient Express Diagnostics",
        "Notes": "",
    },
    # --- Reference interval: empty ---
    {
        "Date": "10-Jan-2024",
        "Test Type": "Biochemistry",
        "Analyte": "Glucose (fasting)",
        "Result": "4.8",
        "Unit": "mmol/L",
        "Reference Interval": "",
        "Collection": "St Mary Mead Clinic",
        "Notes": "",
    },
    # --- FIT test — normalised from typo variant of test type name ---
    {
        "Date": "22-Sep-2023",
        "Test Type": "Quantitv faecal immunochem tst",
        "Analyte": "Faecal haemoglobin",
        "Result": "2",
        "Unit": "μg Hb/g faeces",
        "Reference Interval": "< 10",
        "Collection": "St Mary Mead Clinic",
        "Notes": "",
    },
    # --- Exact duplicate of first row — for deduplication tests ---
    {
        "Date": "6-Apr-2023",
        "Test Type": "Biochemistry",
        "Analyte": "ALT (Alanine aminotransferase)",
        "Result": "32",
        "Unit": "U/L",
        "Reference Interval": "7-56",
        "Collection": "St Mary Mead Clinic",
        "Notes": "",
    },
    # --- Unknown collection site — for unknown-value detection tests ---
    {
        "Date": "3-Mar-2025",
        "Test Type": "Hematology",
        "Analyte": "Haemoglobin",
        "Result": "13.2",
        "Unit": "g/dL",
        "Reference Interval": "11.5-16.5",
        "Collection": "The Mousetrap Medical Centre",
        "Notes": "",
    },
    # --- Unknown analyte — for unknown-value detection tests ---
    {
        "Date": "3-Mar-2025",
        "Test Type": "Biochemistry",
        "Analyte": "Cortisol (morning)",
        "Result": "380",
        "Unit": "nmol/L",
        "Reference Interval": "171-536",
        "Collection": "St Mary Mead Clinic",
        "Notes": "",
    },
]


# A minimal valid single row — useful when a test only needs one clean record
SINGLE_BLOOD_TEST_ROW = BLOOD_TEST_ROWS[0]


# ---------------------------------------------------------------------------
# Menoscale — menoscale tab
# ---------------------------------------------------------------------------
# Two date formats appear in this tab (see blood-tests-schema.md).

MENOSCALE_ROWS = [
    # Format 1: hyphen-separated
    {"Date": "6-Sep-2024", "Score (out of 100)": 14},
    # Format 2: space-separated
    {"Date": "16 Apr 2025", "Score (out of 100)": 19},
    # Full month name — future-proofing the parser
    {"Date": "1 January 2026", "Score (out of 100)": 22},
]


# ---------------------------------------------------------------------------
# Medications — Medications tab
# ---------------------------------------------------------------------------

MEDICATION_ROWS = [
    # Normal ongoing medication
    {
        "Medication Name": "Omeprazole",
        "Dosage": "20mg",
        "Start Date": "2022-03-01",
        "End Date": None,
        "Frequency (times/day)": 1.0,
        "Notes": "Take 30 minutes before food",
    },
    # Medication that has ended
    {
        "Medication Name": "Simvastatin",
        "Dosage": "10mg",
        "Start Date": "2021-06-15",
        "End Date": "2023-11-30",
        "Frequency (times/day)": 1.0,
        "Notes": "",
    },
    # Frequency = 0 (paused/stopped)
    {
        "Medication Name": "Ferrous Sulfate",
        "Dosage": "200mg",
        "Start Date": "2023-01-10",
        "End Date": None,
        "Frequency (times/day)": 0,
        "Notes": "Paused — GI side effects",
    },
    # Alternate days (0.5 frequency)
    {
        "Medication Name": "Centrum Advance",
        "Dosage": "1 tablet",
        "Start Date": "2023-05-01",
        "End Date": None,
        "Frequency (times/day)": 0.5,
        "Notes": "Alternate days",
    },
    # Clinically significant medication
    {
        "Medication Name": "Metyrapone",
        "Dosage": "250mg",
        "Start Date": "2023-08-01",
        "End Date": None,
        "Frequency (times/day)": 2.0,
        "Notes": "Monitor cortisol and ALT",
    },
]


# ---------------------------------------------------------------------------
# Vaccines — Vaccines tab
# ---------------------------------------------------------------------------
# Contains both Poirot and Hastings rows.
# Ingestion must filter to Poirot only — Hastings rows must be discarded.

VACCINE_ROWS = [
    # Poirot — normal row
    {
        "Name": "Poirot",
        "Date Given": "2023-10-05",
        "Vaccine Name & Dose": "Flu (Influenza)",
        "Immunity Duration (Years)": "1 year",
        "Booster Due": 2024.0,
        "Notes": "",
    },
    # Poirot — no trailing space (fixed in source)
    {
        "Name": "Poirot",
        "Date Given": "2023-10-05",
        "Vaccine Name & Dose": "Covid-19",
        "Immunity Duration (Years)": "6 months",
        "Booster Due": 2024.0,
        "Notes": "",
    },
    # Poirot — multi-dose vaccine (1st of 3)
    {
        "Name": "Poirot",
        "Date Given": "2022-04-12",
        "Vaccine Name & Dose": "HPV (1st dose)",
        "Immunity Duration (Years)": "Part of 3-dose course",
        "Booster Due": None,
        "Notes": "",
    },
    # Poirot — booster due as unparseable string → both fields must be NULL
    {
        "Name": "Poirot",
        "Date Given": "2019-07-20",
        "Vaccine Name & Dose": "Typhoid",
        "Immunity Duration (Years)": "3 years",
        "Booster Due": "See 3rd dose date",
        "Notes": "There is a more recent record",
    },
    # Poirot — lifelong immunity, NULL booster
    {
        "Name": "Poirot",
        "Date Given": "2005-09-01",
        "Vaccine Name & Dose": "Hepatitis A (Hep A)",
        "Immunity Duration (Years)": "Lifelong",
        "Booster Due": None,
        "Notes": "",
    },
    # Hastings — must be filtered out
    {
        "Name": "Hastings",
        "Date Given": "2023-10-05",
        "Vaccine Name & Dose": "Flu (Influenza)",
        "Immunity Duration (Years)": "1 year",
        "Booster Due": 2024.0,
        "Notes": "",
    },
    # Hastings — second row to confirm the filter catches all, not just the first
    {
        "Name": "Hastings",
        "Date Given": "2022-11-01",
        "Vaccine Name & Dose": "Covid-19",
        "Immunity Duration (Years)": "6 months",
        "Booster Due": 2023.0,
        "Notes": "",
    },
]


# Convenience: only the Poirot rows — expected output after name filter applied
POIROT_VACCINE_ROWS = [r for r in VACCINE_ROWS if r["Name"].strip() == "Poirot"]
