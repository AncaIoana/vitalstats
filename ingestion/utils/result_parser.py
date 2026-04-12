from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ParsedResult:
    is_numeric: bool
    numeric: float | None = None
    qualifier: str | None = None
    text: str | None = None


# Compiled regex patterns
_LT_PATTERN = re.compile(r'^[<＜]\s*(\d+\.?\d*)$')
_GT_PATTERN = re.compile(r'^[>＞]\s*(\d+\.?\d*)$')


def parse_result(raw: str) -> ParsedResult:
    """Parse a raw result string into a structured ParsedResult.

    Handles five cases:
    - Less-than qualifier: "< 0.6", "<35"       → numeric=0.6, qualifier="lt"
    - Greater-than qualifier: ">120"             → numeric=120, qualifier="gt"
    - Plain numeric: "46", "2.45"               → numeric=46.0
    - Known categorical: "negative", "Positive" → text="negative"
    - Free text: "Discussed with patient"        → text="discussed_with_patient"
    """
    raw = raw.strip()

    # Less-than qualifier
    m = _LT_PATTERN.match(raw)
    if m:
        return ParsedResult(is_numeric=True, numeric=float(m.group(1)), qualifier="lt")

    # Greater-than qualifier
    m = _GT_PATTERN.match(raw)
    if m:
        return ParsedResult(is_numeric=True, numeric=float(m.group(1)), qualifier="gt")

    # Plain numeric
    try:
        return ParsedResult(is_numeric=True, numeric=float(raw))
    except ValueError:
        pass

    # Categorical or free text
    normalised = "_".join(raw.lower().split())
    return ParsedResult(is_numeric=False, text=normalised)
