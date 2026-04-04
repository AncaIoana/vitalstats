"""
Thin wrapper around the Google Sheets API v4.

Responsible only for authentication and fetching raw tab data.
All parsing, validation, and loading is handled by 
extract_blood_tests.py and extract_menoscale.py.
"""

import json
import os
from pathlib import Path
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def _get_credentials() -> Credentials:
    """
    Load service account credentials from the environment.

    Supports two formats for GOOGLE_SHEETS_CREDENTIALS:
    - A file path to a service account JSON file (local development)
    - The full JSON string (CI/CD and production environments)

    Raises:
        EnvironmentError: if the variable is not set.
        ValueError: if the value is neither a valid path nor valid JSON.
    """
    raw = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
    if not raw:
        raise EnvironmentError(
            "GOOGLE_SHEETS_CREDENTIALS environment variable is not set. "
            "Set it to the path of your service account JSON file, "
            "or the full JSON string."
        )

    raw = raw.strip()

    # If it looks like a file path, read the file
    path = Path(raw)
    if path.exists() and path.suffix == ".json":
        with open(path, encoding="utf-8") as f:
            info = json.load(f)
        return Credentials.from_service_account_info(info, scopes=SCOPES)

    # Otherwise treat it as a JSON string
    try:
        info = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"GOOGLE_SHEETS_CREDENTIALS is neither a valid file path "
            f"nor valid JSON: {e}"
        ) from e

    return Credentials.from_service_account_info(info, scopes=SCOPES)


def fetch_tab(sheet_id: str, tab_name: str) -> list[dict[str, Any]]:
    """
    Fetch all rows from a Google Sheet tab as a list of dicts.

    Empty rows (where every field is None or empty string) are filtered out.
    The first row is treated as the header. All subsequent rows are zipped
    with the header to produce dicts. Short rows (fewer fields than the header)
    are padded with None.

    Args:
        sheet_id: the Google Sheet ID from the URL.
        tab_name: the exact tab name to fetch, e.g. "blood_tests_bulk".

    Returns:
        A list of dicts, one per non-empty data row.

    Raises:
        EnvironmentError: if credentials are not configured.
        googleapiclient.errors.HttpError: if the API call fails.
    """
    creds = _get_credentials()
    service = build("sheets", "v4", credentials=creds)

    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=tab_name)
        .execute()
    )

    all_rows: list[list] = result.get("values", [])
    if not all_rows:
        return []

    # Strip trailing whitespace from all header names (handles "Notes " etc.)
    headers = [str(h).strip() for h in all_rows[0]]
    data_rows = all_rows[1:]

    rows_as_dicts = []
    for raw_row in data_rows:
        # Pad short rows so every row has the same number of fields as the header
        padded = raw_row + [None] * (len(headers) - len(raw_row))
        row_dict = dict(zip(headers, padded))

        # Skip rows where every value is None or empty string
        if all(v is None or v == "" for v in row_dict.values()):
            continue

        rows_as_dicts.append(row_dict)

    return rows_as_dicts
