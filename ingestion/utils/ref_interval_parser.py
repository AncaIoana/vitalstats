from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ParsedRefInterval:
    ref_type: str
    ref_low: float | None = None
    ref_high: float | None = None
    note: str | None = None


_KNOWN_PREFIXES = ["adults:", "female:", "male:", "children:", "women:", "men:"]
_NARRATIVE_TRIGGERS = [" for ", "Men", "Women", "Male", "Female", "Pregnancy", "a.m.", "p.m."]

# Matches "35-50", "2.20 - 2.60", "15.00-150.00ug/L"
_RANGE_PATTERN = re.compile(r'^(\d+\.?\d*)\s*-\s*(\d+\.?\d*)')
# Matches "<35", "< 20"
_LT_PATTERN = re.compile(r'^[<＜]\s*(\d+\.?\d*)')
# Matches ">1.99", ">120"
_GT_PATTERN = re.compile(r'^[>＞]\s*(\d+\.?\d*)')


def parse_ref_interval(raw_ref_interval: str) -> ParsedRefInterval:
    """Parse a raw reference interval string into a structured ParsedRefInterval.

    Returns ref_type of:
      - "unknown"     : empty string
      - "categorical" : "N/A"
      - "range"       : "35-50", "2.20 - 2.60", "15.00-150.00ug/L"
      - "lt"          : "<35", "< 20", "Adults: <1.2"
      - "gt"          : ">1.99 %"
      - "narrative"   : gender/age/condition splits, ordinal scales,
                        time-of-day splits, or any unrecognised format

    Known qualifying prefixes (Adults:, Female:, Male: etc.) are stripped
    before parsing. The qualifier is preserved in the note field.
    """
    original_raw_ref_interval = raw_ref_interval
    raw_ref_interval = raw_ref_interval.strip()
    qualifier = None

    if not raw_ref_interval:
        return ParsedRefInterval(ref_type="unknown")

    if raw_ref_interval.upper() == "N/A":
        return ParsedRefInterval(ref_type="categorical")

    for prefix in _KNOWN_PREFIXES:
        if raw_ref_interval.lower().startswith(prefix):
            qualifier = prefix[:-1].strip()
            raw_ref_interval = raw_ref_interval.split(":", 1)[1].strip()
            break

    prefix_note = f"Reference range applies to: {qualifier}" if qualifier else None

    for trigger in _NARRATIVE_TRIGGERS:
        if trigger.lower() in raw_ref_interval.lower():
            return ParsedRefInterval(ref_type="narrative",
                                     note=original_raw_ref_interval)

    m = _RANGE_PATTERN.match(raw_ref_interval)
    if m:
        return ParsedRefInterval(ref_type="range",
                                 ref_low=float(m.group(1)),
                                 ref_high=float(m.group(2)),
                                 note=prefix_note)

    m = _LT_PATTERN.match(raw_ref_interval)
    if m:
        return ParsedRefInterval(ref_type="lt",
                                 ref_high=float(m.group(1)),
                                 note=prefix_note)

    m = _GT_PATTERN.match(raw_ref_interval)
    if m:
        return ParsedRefInterval(ref_type="gt",
                                 ref_low=float(m.group(1)),
                                 note=prefix_note)

    return ParsedRefInterval(ref_type="narrative",
                             note=original_raw_ref_interval)
