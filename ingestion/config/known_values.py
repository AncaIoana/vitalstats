"""
Single source of truth for expected test types and collection sites.
Any value arriving from the source that is not listed here triggers
detection logic in the ingestion pipeline.
"""

# Maps every raw test type string we've seen in the source to its canonical slug.
# If a raw value arrives that is NOT in this dict, treat as a hard failure.
KNOWN_TEST_TYPES: dict[str, str] = {
    "Biochemistry": "biochemistry",
    "Hematology": "hematology",
    "Immunochemistry": "immunochemistry",
    "Microbiology": "microbiology",
    "Endocrinology": "endocrinology",
    "Coagulation": "coagulation",
}

# Maps every raw collection site string to its canonical slug and metadata.
#
# unit_system values follow IFCC terminology:
#   "SI"           — international standard (mmol/L, μmol/L, nmol/L etc.)
#                    Used by NHS and most European labs.
#   "conventional" — older conventional units (mg/dL etc.)
#                    Used as the primary system by some labs 
#
# Note: unit_system describes the lab's PRIMARY convention, not a guarantee
# that every analyte uses that system. Per-analyte unit conversion is always
# handled in dbt by inspecting the unit column directly. This field tells dbt
# where to expect conversion work to be concentrated.
#
# If a raw value arrives that is NOT in this dict, ingest the row but set
# pipeline_run_log.status = "partial" and log to silver.stg_unknown_values.
KNOWN_COLLECTION_SITES: dict[str, dict] = {
    "New Islington Medical Practice": {
        "slug": "new_islington_gp",
        "country": "UK",
        "unit_system": "SI",
    },
    "Salford Royal": {
        "slug": "salford_royal",
        "country": "UK",
        "unit_system": "SI",
    },
    "Nuffield Health": {
        "slug": "nuffield_health",
        "country": "UK",
        "unit_system": "SI",
    },
    "Pall Mall": {
        "slug": "pall_mall",
        "country": "UK",
        "unit_system": "SI",
    },
    "Synevo": {
        "slug": "synevo",
        "country": "Romania",
        "unit_system": "conventional",
    },
}

# Columns we expect to find in blood_tests_bulk.
EXPECTED_COLUMNS_BLOOD_TESTS: list[str] = [
    "Date",
    "Test Type",
    "Analyte",
    "Result",
    "Unit",
    "Reference Interval",
    "Collection",
    "Notes",
]

# Columns we expect to find in menoscale.
EXPECTED_COLUMNS_MENOSCALE: list[str] = [
    "Date",
    "Score (out of 100)",
]
