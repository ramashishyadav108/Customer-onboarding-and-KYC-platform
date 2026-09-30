"""NFR-06 / E1-S1 AC2: JSON logs with correlation id and case id (F003, F004, F005)."""

import json
import logging
import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

REQUIRED_KEYS = {"timestamp", "level", "correlation_id", "message"}


def _lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    out = capsys.readouterr().out
    parsed: list[dict[str, Any]] = []
    for line in out.splitlines():
        if line.strip():
            parsed.append(json.loads(line))
    return parsed


def test_nfr06_every_log_line_is_single_line_json_with_required_keys(
    app: FastAPI, capsys: pytest.CaptureFixture[str]
) -> None:
    """NFR-06 (F003): every captured line parses as JSON with the four required keys."""
    with TestClient(app) as client:
        client.get("/health")
    raw = capsys.readouterr().out
    assert raw.strip(), "expected at least one log line"
    for line in raw.splitlines():
        record = json.loads(line)
        assert REQUIRED_KEYS <= set(record)


def test_nfr06_multiline_messages_stay_on_one_line(
    app: FastAPI, capsys: pytest.CaptureFixture[str]
) -> None:
    """NFR-06 (F003): newlines inside a message are escaped, never emitted raw."""
    with TestClient(app):
        logging.getLogger("onboardx.test").info("first\nsecond")
    lines = [line for line in capsys.readouterr().out.splitlines() if "first" in line]
    assert len(lines) == 1
    assert json.loads(lines[0])["message"] == "first\nsecond"


def test_nfr06_correlation_header_is_echoed_and_logged(
    app: FastAPI, capsys: pytest.CaptureFixture[str]
) -> None:
    """NFR-06 (F004): X-Correlation-ID abc-123 appears in the response header and log lines."""
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Correlation-ID": "abc-123"})
    assert response.headers["X-Correlation-ID"] == "abc-123"
    records = _lines(capsys)
    assert records
    assert {r["correlation_id"] for r in records} >= {"abc-123"}


def test_nfr06_missing_header_generates_uuid4(
    app: FastAPI, capsys: pytest.CaptureFixture[str]
) -> None:
    """NFR-06 (F004): no header -> a UUID4 is generated, echoed and logged."""
    with TestClient(app) as client:
        response = client.get("/health")
    generated = response.headers["X-Correlation-ID"]
    assert uuid.UUID(generated).version == 4
    records = _lines(capsys)
    assert generated in {r["correlation_id"] for r in records}


def test_nfr06_unsafe_correlation_header_is_replaced(app: FastAPI) -> None:
    """NFR-06: an over-long or control-character header is not trusted; a UUID4 is used."""
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Correlation-ID": "x" * 300})
    assert uuid.UUID(response.headers["X-Correlation-ID"]).version == 4


def test_nfr06_case_scoped_request_logs_case_id(
    app: FastAPI, capsys: pytest.CaptureFixture[str]
) -> None:
    """NFR-06 (F005): lines for a route with a case_id path parameter carry case_id."""
    case_id = str(uuid.uuid4())

    @app.get("/test-only/cases/{case_id}")
    def case_scoped(case_id: str) -> dict[str, str]:
        logging.getLogger("onboardx.test").info("inside handler")
        return {"case_id": case_id}

    with TestClient(app) as client:
        client.get(f"/test-only/cases/{case_id}")
    records = _lines(capsys)
    inside = [r for r in records if r["message"] == "inside handler"]
    assert inside
    assert inside[0]["case_id"] == case_id
    assert any(r.get("case_id") == case_id for r in records)


def test_nfr06_request_log_contains_no_query_string_or_body(
    app: FastAPI, capsys: pytest.CaptureFixture[str]
) -> None:
    """NFR-03 / NFR-06: request logging records method, path and status only."""
    with TestClient(app) as client:
        client.get("/health?email=test.person@example.com")
    out = capsys.readouterr().out
    assert "test.person" not in out
    assert any(r.get("status") == 200 for r in map(json.loads, out.splitlines()))
