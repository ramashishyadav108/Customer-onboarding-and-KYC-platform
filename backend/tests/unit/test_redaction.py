"""NFR-03 / E1-S1 AC3: PII redaction in log output (F006)."""

import io
import json
import logging

import pytest

from onboardx.config.logging_setup import JsonFormatter
from onboardx.config.redaction import REDACTION_MARKER, RedactionFilter, redact_text

PAN = "ABCDE1234F"
AADHAAR = "123412341234"
PHONE = "9876543210"
EMAIL = "test.person@example.com"
INCOME = "3000000"
OCCUPATION = "SELF_EMPLOYED"
ALL_VALUES = [PAN, AADHAAR, PHONE, EMAIL, INCOME, OCCUPATION]


def _logger(name: str) -> tuple[logging.Logger, io.StringIO]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter())
    logger = logging.getLogger(name)
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    return logger, stream


def test_ac3_message_pii_is_redacted() -> None:
    """AC-03 (E1-S1 AC3): PAN, Aadhaar, phone, email, income, occupation in the message."""
    logger, stream = _logger("redaction.message")
    logger.info(
        "applicant PAN %s aadhaar %s phone %s email %s annual_income=%s occupation: %s",
        PAN,
        "1234 1234 1234",
        PHONE,
        EMAIL,
        INCOME,
        OCCUPATION,
    )
    out = stream.getvalue()
    for value in (PAN, AADHAAR, "1234 1234 1234", PHONE, EMAIL, INCOME, OCCUPATION):
        assert value not in out
    assert REDACTION_MARKER in out


def test_ac3_extra_fields_are_redacted() -> None:
    """NFR-03: PII in extra fields is redacted by key name and by value pattern."""
    logger, stream = _logger("redaction.extra")
    logger.info(
        "profile saved",
        extra={
            "pan": PAN,
            "aadhaar": AADHAAR,
            "phone": PHONE,
            "email": EMAIL,
            "annual_income": INCOME,
            "occupation_category": OCCUPATION,
            "note": f"call {PHONE} or mail {EMAIL}",
            "nested": {"income": INCOME, "tags": [PAN]},
        },
    )
    out = stream.getvalue()
    for value in ALL_VALUES:
        assert value not in out
    assert REDACTION_MARKER in out
    json.loads(out)


def test_nfr03_formatter_redacts_without_filter() -> None:
    """NFR-03: the formatter redacts on its own, so a missing filter cannot leak PII."""
    record = logging.LogRecord("x", logging.INFO, __file__, 1, f"pan {PAN}", None, None)
    assert PAN not in JsonFormatter().format(record)


def test_nfr03_non_pii_text_is_unchanged() -> None:
    """NFR-03: case ids and ordinary text are not redacted."""
    text = "case 3f0c2c9e-7a54-4b7e-9d3e-5b1f6a2e9c10 moved to SCREENED in 12 ms"
    assert redact_text(text) == text


@pytest.mark.parametrize("raw", ["+91 9876543210", "91-9876543210", "0987654321"])
def test_nfr03_phone_formats(raw: str) -> None:
    """NFR-03: phone numbers with prefixes are redacted."""
    assert "987654321" not in redact_text(f"call {raw} now")


def test_nfr03_exception_text_is_redacted() -> None:
    """NFR-03: exception tracebacks are redacted too."""
    logger, stream = _logger("redaction.exc")
    try:
        raise ValueError(f"bad email {EMAIL}")
    except ValueError:
        logger.exception("failed")
    assert EMAIL not in stream.getvalue()
