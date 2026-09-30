"""PII redaction for log output (NFR-03): PAN, Aadhaar, phone, email, income, occupation."""

import logging
import re
from typing import Any

REDACTION_MARKER = "[REDACTED]"

PII_KEYS = frozenset(
    {
        "pan",
        "aadhaar",
        "aadhar",
        "phone",
        "mobile",
        "email",
        "contact",
        "full_name",
        "prospect_name",
        "date_of_birth",
        "dob",
        "annual_income",
        "income",
        "occupation",
        "occupation_category",
    }
)

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_KEY_VALUE = re.compile(
    r"""(?ix)\b(annual[_ ]?income|income|occupation(?:[_ ]category)?)\b
        (["']?\s*(?:[:=]|\bis\b|\bof\b)?\s*["']?)
        ([^\s,;}\]"']+)"""
)
_PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
_AADHAAR = re.compile(r"(?<![\w-])\d{4}[ -]?\d{4}[ -]?\d{4}(?![\w-])")
_PHONE = re.compile(r"(?<![\w-])(?:\+?91[ -]?)?0?\d{10}(?![\w-])")
_OCCUPATION = re.compile(
    r"\b(?:SALARIED|SELF_EMPLOYED|BUSINESS_OWNER|STUDENT|RETIRED|CASH_INTENSIVE)\b"
)

_STANDARD_RECORD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | {"message", "asctime", "taskName"}


def redact_text(text: str) -> str:
    """Replace every PII pattern found in free text with the redaction marker."""
    text = _EMAIL.sub(REDACTION_MARKER, text)
    text = _KEY_VALUE.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTION_MARKER}", text)
    for pattern in (_PAN, _AADHAAR, _PHONE, _OCCUPATION):
        text = pattern.sub(REDACTION_MARKER, text)
    return text


def redact_value(key: str, value: Any) -> Any:
    """Redact a structured field: by key name first, then by value content."""
    if key.lower() in PII_KEYS:
        return REDACTION_MARKER
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {str(k): redact_value(str(k), v) for k, v in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [redact_value(key, item) for item in value]
    if isinstance(value, int) and not isinstance(value, bool):
        return REDACTION_MARKER if redact_text(str(value)) != str(value) else value
    return value


class RedactionFilter(logging.Filter):
    """Handler filter that rewrites the message and extra fields of every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage())
        record.args = None
        for key in set(record.__dict__) - _STANDARD_RECORD_ATTRS:
            setattr(record, key, redact_value(key, record.__dict__[key]))
        return True
