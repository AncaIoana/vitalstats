"""
Row hashing utilities for vitalStats ingestion scripts

Every source row is hashed (SHA-256) before loading. On each pipeline run,
incoming hashes are compared against the raw table. Only rows with new hashes
are inserted, which detects both new rows and edits to existing rows.
"""

import hashlib
import json


def hash_row(row: dict) -> str:
    """
    Compute a stable SHA-256 hash of a source row.

    Fields are sorted by key before hashing so that dict ordering never
    affects the result. Values are serialised to strings via JSON to ensure
    consistent representation across types (None, int, float, str).

    Args:
        row: a dict of field names to raw values, exactly as received
             from the source before any parsing or transformation.

    Returns:
        A 64-character lowercase hex string.
    """
    normalised = {k: v for k, v in sorted(row.items())}
    serialised = json.dumps(normalised, default=str, ensure_ascii=False)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()
