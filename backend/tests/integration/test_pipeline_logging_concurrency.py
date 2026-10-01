"""NFR-03 / NFR-06 logging across the whole pipeline, and race safety of submit and advance."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from api_helpers import create_lead, staff_headers
from helpers import JWT_SECRET, FakeClock
from onboardx.config.settings import Settings
from onboardx.controllers.dependencies.services import Services
from onboardx.main import create_app
from pipeline_helpers import history, put_profile, rows, upload_all, upload_ok

NAME = "Zorblax Quentinsen"
EMAIL = "zorblax.quentinsen@example.com"
PAN = "ABCDE1234F"
INCOME = 7654321
PROFILE = {
    "date_of_birth": "1991-07-19",
    "annual_income": INCOME,
    "occupation_category": "SELF_EMPLOYED",
    "country_code": "IN",
    "state_code": "MH",
}


def parse(output: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in output.splitlines() if line.strip()]


@pytest.mark.nfr("NFR-03")
def test_nfr03_no_plaintext_pii_in_logs_across_the_whole_pipeline(
    auto_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    """Drives lead, profile, upload, reject, submit, screen, classify, decide, advance and error
    paths; no name, contact, PAN, income or occupation string may appear in any log line."""
    capsys.readouterr()
    lead = create_lead(auto_client, name=NAME, contact=EMAIL)
    put_profile(auto_client, lead, PROFILE)
    upload_ok(auto_client, lead, "ID_PROOF", f"pan_{PAN}.pdf")
    upload_ok(auto_client, lead, "ID_PROOF", f"pan_{PAN}_v2.pdf")
    upload_all(auto_client, lead, "Savings", {"ID_PROOF": f"aadhaar_{PAN}.jpg"})
    staff = staff_headers(auto_client)
    case = f"/api/v1/cases/{lead['case_id']}"
    docs = auto_client.get(f"{case}/documents", headers=staff).json()["documents"]
    auto_client.post(
        f"{case}/documents/{docs[0]['document_id']}/reject",
        json={"reason_code": "DOC_OTHER", "comment": f"{NAME} {EMAIL}"},
        headers=staff,
    )
    auto_client.post(
        f"{case}/documents", data={"checklist_item": "ID_PROOF"},
        files={"file": (f"{NAME}.txt", b"x", "text/plain")},
        headers={"Authorization": f"Bearer {lead['access_token']}"},
    )  # fmt: skip
    for name in ("submit", "advance", "screen", "classify", "decide"):
        auto_client.post(f"{case}/{name}", headers=staff)
    auto_client.get(f"{case}/notifications", headers=staff)
    out = capsys.readouterr().out
    assert out.strip()
    for secret in (NAME, "Zorblax", "Quentinsen", EMAIL, "example.com", PAN, str(INCOME)):
        assert secret not in out, secret
    for label in ("SELF_EMPLOYED", "occupation", "annual_income", "1991-07-19"):
        assert label not in out, label


@pytest.mark.nfr("NFR-06")
def test_nfr06_every_pipeline_log_line_is_json_with_correlation_id_and_case_id(
    auto_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    lead = create_lead(auto_client)
    put_profile(auto_client, lead, PROFILE)
    upload_all(auto_client, lead, "Savings")
    response = auto_client.post(
        f"/api/v1/cases/{lead['case_id']}/submit",
        headers={
            "Authorization": f"Bearer {lead['access_token']}",
            "X-Correlation-ID": "corr-pipeline-1",
        },
    )
    assert response.status_code == 200
    lines = parse(capsys.readouterr().out)
    submit_lines = [line for line in lines if line["correlation_id"] == "corr-pipeline-1"]
    messages = {line["message"] for line in submit_lines}
    assert {
        "case screened",
        "case classified",
        "decision recorded",
        "pipeline advanced",
        "request completed",
    } <= messages
    assert all(line.get("case_id") == lead["case_id"] for line in submit_lines)
    assert all({"timestamp", "level", "logger"} <= set(line) for line in lines)


@pytest.mark.nfr("NFR-03")
def test_nfr03_screening_logs_carry_the_hit_count_but_not_the_list_details(
    auto_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC-05.10: case_id and hit count only."""
    capsys.readouterr()
    lead = create_lead(auto_client, name="Test Person One")
    put_profile(auto_client, lead, PROFILE)
    upload_all(auto_client, lead, "Savings")
    auto_client.post(
        f"/api/v1/cases/{lead['case_id']}/submit",
        headers={"Authorization": f"Bearer {lead['access_token']}"},
    )
    out = capsys.readouterr().out
    (screened,) = [line for line in parse(out) if line["message"] == "case screened"]
    assert screened["hit_count"] == 1 and screened["case_id"] == lead["case_id"]
    assert "Test Person" not in out and "AML_HIT" not in out.split("decision recorded")[0]
    assert "10000000-0000-4000-8000-000000000001" not in out


@pytest.fixture
def shared_services(db_url: str, upload_dir: Path, clock: FakeClock) -> Services:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        database_url=db_url,
        jwt_secret=JWT_SECRET,
        upload_dir=upload_dir,
        auto_advance_on_submit=False,
    )
    services: Services = create_app(settings, clock=clock).state.services
    return services


def run_parallel(count: int, task: Any) -> list[Any]:
    barrier = threading.Barrier(count)

    def wrapped(index: int) -> Any:
        barrier.wait()
        try:
            return task(index)
        except Exception as error:
            return error

    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(wrapped, range(count)))


@pytest.mark.ac("AC-07")
def test_ac07_concurrent_advance_calls_never_duplicate_history_or_decisions(
    client: TestClient, engine: Engine, shared_services: Services
) -> None:
    """Race safety: parallel advance calls leave exactly one row per step and one decision."""
    lead = create_lead(client)
    put_profile(client, lead, PROFILE)
    upload_all(client, lead, "Savings")
    client.post(
        f"/api/v1/cases/{lead['case_id']}/submit",
        headers={"Authorization": f"Bearer {lead['access_token']}"},
    )
    outcomes = run_parallel(
        4,
        lambda _i: shared_services.pipeline.advance(
            case_id=lead["case_id"], actor="system", role="system"
        ),
    )
    assert any(not isinstance(o, Exception) for o in outcomes)
    final = shared_services.pipeline.advance(case_id=lead["case_id"], actor="system", role="system")
    assert final.state == "APPROVED" and final.steps_run == ()
    path = history(engine, lead["case_id"])
    assert path == ["INITIATED", "DOCS_SUBMITTED", "SCREENED", "CLASSIFIED", "APPROVED"]
    for table in ("decisions", "accounts", "risk_assessments"):
        assert rows(engine, f"SELECT COUNT(*) FROM {table}")[0][0] == 1, table
    assert rows(engine, "SELECT COUNT(*) FROM notifications")[0][0] == 5


@pytest.mark.ac("AC-02")
def test_ac02_9_concurrent_submits_create_a_single_docs_submitted_row(
    client: TestClient, engine: Engine, shared_services: Services
) -> None:
    lead = create_lead(client)
    put_profile(client, lead, PROFILE)
    upload_all(client, lead, "Savings")
    outcomes = run_parallel(
        4,
        lambda _i: shared_services.submission.submit(
            case_id=lead["case_id"], actor=f"prospect:{lead['case_id']}"
        ),
    )
    assert any(not isinstance(o, Exception) for o in outcomes)
    assert history(engine, lead["case_id"]) == ["INITIATED", "DOCS_SUBMITTED"]
    assert (
        rows(engine, "SELECT COUNT(*) FROM audit_log WHERE event='DOCUMENTS_SUBMITTED'")[0][0] == 1
    )


@pytest.mark.ac("AC-09")
def test_ac09_3b_concurrent_uploads_to_one_item_produce_distinct_versions(
    client: TestClient, engine: Engine, shared_services: Services
) -> None:
    lead = create_lead(client)
    outcomes = run_parallel(
        3,
        lambda i: shared_services.documents.upload(
            case_id=lead["case_id"],
            actor="prospect",
            checklist_item="ID_PROOF",
            filename=f"pan_{i}.pdf",
            content_type="application/pdf",
            content=b"x" * (i + 1),
        ),
    )
    ok = [o for o in outcomes if not isinstance(o, Exception)]
    assert ok
    versions = [r[0] for r in rows(engine, "SELECT version FROM documents ORDER BY version")]
    assert versions == list(range(1, len(ok) + 1))
