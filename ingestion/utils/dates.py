"""
Date parsing utilities for vitalStats ingestion scripts.

The Google Sheets API returns dates as strings. The format varies by tab —
blood_tests_bulk uses "D-Mon-YYYY" consistently; other tabs may differ.
"""

from datetime import date, datetime


def parse_blood_test_date(raw: str) -> date:
    """
    Parse a date string from blood_tests_bulk tab.

    Expected input: "D-Mon-YYYY" e.g. "6-Apr-2023", "27-Feb-2023"
    Output format:          ISO date      e.g. date(2023, 4, 6)

    Raises:
        ValueError: if the string cannot be parsed.
    """
    if not raw or not raw.strip():
        raise ValueError("Date value is empty or whitespace")
    return datetime.strptime(raw.strip(), "%d-%b-%Y").date()
