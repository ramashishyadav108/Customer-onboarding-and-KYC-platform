"""E4-S4 / AC-09: stubbed notifications per state entered, owner-only read, no plaintext contact."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from api_helpers import create_lead, lead_headers, staff_headers
from helpers import FakeClock
from onboardx.config.settings import Settings
from onboardx.main import create_app
from pipeline_helpers import (
    history,
    notifications,
    ready_case,
    reject,
    rows,
    state_of,
    submit,
    submitted_case,
    upload_ok,
)

CONTACT = "9999999921"


@pytest.mark.ac("AC-09")
def test_ac09_1_lead_registration_records_the_initiated_notification(
    client: TestClient, engine: Engine
) -> None:
    """Contract: the INITIATED notification is written with the case in one transaction."""
    lead = create_lead(client)
    (only,) = notifications(client, lead)
    assert only["event"] == "INITIATED" and only["template"] == "notification.initiated"
    assert only["details"] == {} and only["created_at"].endswith("Z")
    assert rows(engine, "SELECT COUNT(*) FROM notifications")[0][0] == 1


@pytest.mark.ac("AC-09")
def test_ac09_1_idempotent_lead_replay_adds_no_second_initiated_notification(
    client: TestClient, engine: Engine
) -> None:
    body = {"name": "Test Person Alpha", "contact": CONTACT, "product": "Savings"}
    headers = {"Idempotency-Key": "k-notify-1"}
    assert client.post("/api/v1/leads", json=body, headers=headers).status_code == 201
    assert client.post("/api/v1/leads", json=body, headers=headers).status_code == 200
    assert rows(engine, "SELECT COUNT(*) FROM notifications")[0][0] == 1


@pytest.mark.ac("AC-09")
def test_ac09_1_exactly_one_notification_per_state_entered_on_the_approved_path(
    auto_client: TestClient, engine: Engine
) -> None:
    lead = ready_case(auto_client)
    submit(auto_client, lead)
    events = [n["event"] for n in notifications(auto_client, lead)]
    assert events == ["APPROVED", "CLASSIFIED", "SCREENED", "DOCS_SUBMITTED", "INITIATED"]
    assert sorted(events) == sorted(history(engine, lead["case_id"]))


@pytest.mark.ac("AC-09")
def test_ac09_1_manual_review_path_notifies_manual_review(auto_client: TestClient) -> None:
    lead = ready_case(auto_client, name="Test Person One")
    submit(auto_client, lead)
    events = [n["event"] for n in notifications(auto_client, lead)]
    assert events[0] == "MANUAL_REVIEW" and events.count("MANUAL_REVIEW") == 1
    assert "APPROVED" not in events


@pytest.mark.ac("AC-09")
def test_ac09_1_each_state_notification_appears_when_the_state_is_entered(
    client: TestClient,
) -> None:
    lead = ready_case(client)
    assert [n["event"] for n in notifications(client, lead)] == ["INITIATED"]
    submit(client, lead)
    assert [n["event"] for n in notifications(client, lead)] == ["DOCS_SUBMITTED", "INITIATED"]
    client.post(f"/api/v1/cases/{lead['case_id']}/screen", headers=staff_headers(client))
    assert notifications(client, lead)[0]["event"] == "SCREENED"


@pytest.mark.ac("AC-09")
def test_ac09_4_notifications_are_newest_first_and_carry_the_contract_fields(
    client: TestClient, clock: FakeClock
) -> None:
    lead = create_lead(client)
    clock.advance(60)
    upload_ok(client, lead, "ID_PROOF", "pan_1.pdf")
    clock.advance(60)
    response = client.get(
        f"/api/v1/cases/{lead['case_id']}/notifications", headers=lead_headers(lead)
    )
    body = response.json()
    assert set(body) == {"case_id", "notifications"} and body["case_id"] == lead["case_id"]
    assert set(body["notifications"][0]) == {
        "notification_id", "case_id", "event", "template", "text", "details", "created_at",
    }  # fmt: skip


@pytest.mark.ac("AC-09")
def test_ac09_4_newest_first_ordering_uses_append_order(client: TestClient) -> None:
    lead = submitted_case(client)
    client.post(f"/api/v1/cases/{lead['case_id']}/advance", headers=staff_headers(client))
    stamps = [n["created_at"] for n in notifications(client, lead)]
    assert stamps == sorted(stamps, reverse=True)


@pytest.mark.ac("AC-09")
def test_ac09_4_another_prospect_gets_403(client: TestClient) -> None:
    lead = create_lead(client)
    other = create_lead(client, name="Test Person Other")
    response = client.get(
        f"/api/v1/cases/{lead['case_id']}/notifications", headers=lead_headers(other)
    )
    assert response.status_code == 403


@pytest.mark.nfr("NFR-04")
@pytest.mark.parametrize("user", ["analyst1", "officer1", "admin1"])
def test_nfr04_staff_cannot_read_notifications(client: TestClient, user: str) -> None:
    """Contract 2.5: the read is restricted to the owning prospect, staff included."""
    lead = create_lead(client)
    response = client.get(
        f"/api/v1/cases/{lead['case_id']}/notifications", headers=staff_headers(client, user)
    )
    assert response.status_code == 403


@pytest.mark.nfr("NFR-04")
def test_nfr04_notifications_require_a_token(client: TestClient) -> None:
    lead = create_lead(client)
    assert client.get(f"/api/v1/cases/{lead['case_id']}/notifications").status_code == 401


@pytest.mark.ac("AC-09")
def test_ac09_5_notification_rows_and_text_hold_no_plaintext_contact(
    auto_client: TestClient, engine: Engine
) -> None:
    lead = ready_case(auto_client)
    submit(auto_client, lead)
    found = rows(engine, "SELECT text, details, contact_masked, template FROM notifications")
    assert len(found) == 5
    for row in found:
        assert CONTACT not in " ".join(str(c) for c in row)
        assert row[2] == "********21"


@pytest.mark.ac("AC-09")
def test_ac09_5_email_contacts_are_masked_too(client: TestClient, engine: Engine) -> None:
    lead = create_lead(client, contact="zorblax@example.com")
    (row,) = rows(engine, "SELECT text, contact_masked FROM notifications")
    assert "zorblax" not in row[0] + row[1] and row[1].endswith("om") and set(row[1][:-2]) == {"*"}
    assert "example.com" not in json.dumps(notifications(client, lead))


@pytest.mark.ac("AC-09")
def test_ac09_5_notifications_never_disclose_screening_hits_or_risk_reasons(
    auto_client: TestClient,
) -> None:
    """An AML hit must not be tipped off to the applicant through notification text."""
    lead = ready_case(auto_client, name="Test Person One")
    submit(auto_client, lead)
    blob = json.dumps(notifications(auto_client, lead))
    for word in ("AML", "PEP", "watchlist", "RISK_", "HIT"):
        assert word not in blob


@pytest.mark.nfr("NFR-02")
def test_nfr02_notifications_are_unique_per_event_and_append_only(
    client: TestClient, engine: Engine
) -> None:
    lead = create_lead(client)
    duplicate = (
        "INSERT INTO notifications (notification_id, case_id, event, template, text, details,"
        " contact_masked, created_at) VALUES ('dup', :c, 'INITIATED', 't', 'x', '{}', '**', 't')"
    )
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text(duplicate), {"c": lead["case_id"]})
    for statement in ("UPDATE notifications SET text='x'", "DELETE FROM notifications"):
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(text(statement))


@pytest.mark.ac("AC-09")
def test_ac09_2_doc_rejected_notifications_may_repeat_unlike_state_events(
    client: TestClient, engine: Engine
) -> None:
    lead = create_lead(client)
    first = upload_ok(client, lead, "ID_PROOF", "pan_1.pdf")
    reject(client, lead, first["document_id"])
    second = upload_ok(client, lead, "ID_PROOF", "pan_2.pdf")
    reject(client, lead, second["document_id"], "DOC_EXPIRED")
    found = rows(
        engine, "SELECT details FROM notifications WHERE event='DOC_REJECTED' ORDER BY seq"
    )
    assert [json.loads(r[0])["reason_code"] for r in found] == ["DOC_ILLEGIBLE", "DOC_EXPIRED"]


@pytest.fixture
def failing_client(db_url: str, upload_dir: Path, clock: FakeClock) -> Iterator[TestClient]:
    class ExplodingSender:
        def send(self, case_id: str, event: str, text: str) -> None:
            raise RuntimeError(f"channel down for {CONTACT}")

    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        database_url=db_url,
        jwt_secret="x" * 40,
        upload_dir=upload_dir,
        auto_advance_on_submit=True,
    )
    app = create_app(settings, clock=clock, notification_sender=ExplodingSender())
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.ac("AC-09")
def test_ac09_5_a_sender_failure_does_not_roll_back_the_transition(
    failing_client: TestClient, engine: Engine
) -> None:
    """E4-S4 AC5: the lead, every transition and every notification row still commit."""
    lead = ready_case(failing_client)
    assert submit(failing_client, lead).status_code == 200
    assert state_of(failing_client, lead) == "APPROVED"
    assert rows(engine, "SELECT COUNT(*) FROM notifications")[0][0] == 5
    assert history(engine, lead["case_id"])[-1] == "APPROVED"


@pytest.mark.ac("AC-09")
def test_ac09_5_sender_failure_is_logged_with_case_id_and_correlation_id_without_contact(
    failing_client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    response = failing_client.post(
        "/api/v1/leads",
        json={"name": "Test Person Alpha", "contact": CONTACT, "product": "Savings"},
        headers={"X-Correlation-ID": "corr-notify-1"},
    )
    assert response.status_code == 201
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
    failures = [line for line in lines if line["message"] == "notification sender failed"]
    assert len(failures) == 1
    failure = failures[0]
    assert failure["case_id"] == response.json()["case_id"]
    assert failure["correlation_id"] == "corr-notify-1" and failure["level"] == "ERROR"
    assert CONTACT not in json.dumps(failure)
