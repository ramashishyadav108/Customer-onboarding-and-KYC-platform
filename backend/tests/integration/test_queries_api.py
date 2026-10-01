"""AC-13 / NFR-02 / NFR-03 / NFR-04: analyst queries, prospect responses, append-only history."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from api_helpers import bearer, create_lead, lead_headers, staff_headers
from pipeline_helpers import rows, submitted_case

MESSAGE = "Please upload a clearer scan of the address proof"
REPLY = "Re-uploaded a clearer scan this morning"


def raise_query(client: TestClient, lead: dict[str, Any], message: str = MESSAGE) -> Any:
    return client.post(
        f"/api/v1/cases/{lead['case_id']}/queries",
        json={"message": message},
        headers=staff_headers(client, "analyst1"),
    )


def respond(client: TestClient, lead: dict[str, Any], query_id: str, message: str = REPLY) -> Any:
    return client.post(
        f"/api/v1/cases/{lead['case_id']}/queries/{query_id}/responses",
        json={"message": message},
        headers=lead_headers(lead),
    )


def close(client: TestClient, lead: dict[str, Any], query_id: str) -> Any:
    return client.post(
        f"/api/v1/cases/{lead['case_id']}/queries/{query_id}/close",
        headers=staff_headers(client, "analyst1"),
    )


def listing(client: TestClient, lead: dict[str, Any], headers: Any = None) -> Any:
    url = f"/api/v1/cases/{lead['case_id']}/queries"
    return client.get(url, headers=headers or lead_headers(lead))


@pytest.mark.ac("AC-13.1")
def test_ac13_1_analyst_raises_a_query(client: TestClient) -> None:
    lead = create_lead(client)
    response = raise_query(client, lead)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "OPEN" and body["message"] == MESSAGE and body["responses"] == []
    assert body["case_id"] == lead["case_id"] and body["query_id"]


@pytest.mark.ac("AC-13.1")
@pytest.mark.parametrize("message", ["", "x" * 501])
def test_ac13_1_message_length_is_validated(client: TestClient, message: str) -> None:
    lead = create_lead(client)
    assert raise_query(client, lead, message).status_code == 422


@pytest.mark.ac("AC-13.1")
def test_ac13_1_unknown_case_is_404_and_locked_case_is_409(auto_client: TestClient) -> None:
    ghost = {"case_id": "00000000-0000-4000-8000-0000000000ff"}
    assert raise_query(auto_client, ghost).status_code == 404
    approved = submitted_case(auto_client)
    state = auto_client.get(
        f"/api/v1/cases/{approved['case_id']}", headers=staff_headers(auto_client)
    ).json()["state"]
    assert state == "APPROVED"
    locked = raise_query(auto_client, approved)
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "CASE_LOCKED"


@pytest.mark.ac("AC-13.2")
def test_ac13_2_owner_and_staff_can_list_but_other_prospects_cannot(client: TestClient) -> None:
    lead = create_lead(client)
    other = create_lead(client, contact="9999999922")
    qid = raise_query(client, lead).json()["query_id"]
    respond(client, lead, qid)
    mine = listing(client, lead).json()["items"]
    assert [q["query_id"] for q in mine] == [qid] and mine[0]["status"] == "ANSWERED"
    assert mine[0]["responses"][0]["message"] == REPLY
    for role in ("analyst1", "officer1", "admin1"):
        assert listing(client, lead, staff_headers(client, role)).status_code == 200
    assert listing(client, lead, bearer(other["access_token"])).status_code == 403
    assert client.get(f"/api/v1/cases/{lead['case_id']}/queries").status_code == 401


@pytest.mark.ac("AC-13.2")
def test_ac13_2_queries_are_listed_oldest_first(client: TestClient) -> None:
    lead = create_lead(client)
    first = raise_query(client, lead, "first question").json()["query_id"]
    second = raise_query(client, lead, "second question").json()["query_id"]
    assert [q["query_id"] for q in listing(client, lead).json()["items"]] == [first, second]


@pytest.mark.ac("AC-13.3")
def test_ac13_3_response_marks_answered_and_closed_queries_refuse(client: TestClient) -> None:
    lead = create_lead(client)
    qid = raise_query(client, lead).json()["query_id"]
    answered = respond(client, lead, qid)
    assert answered.status_code == 201 and answered.json()["status"] == "ANSWERED"
    assert close(client, lead, qid).status_code == 200
    refused = respond(client, lead, qid)
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "QUERY_CLOSED"
    assert respond(client, lead, "missing").status_code == 404
    assert respond(client, lead, qid, "").status_code == 422


@pytest.mark.ac("AC-13.3")
def test_ac13_3_responding_on_a_locked_case_is_409(auto_client: TestClient, engine: Engine) -> None:
    lead = submitted_case(auto_client, name="Test Person Beta")
    # a query created while the case was open, then the case became terminal
    sql = (
        "INSERT INTO case_queries (query_id, case_id, raised_by, message, created_at)"
        " VALUES ('q-locked', :c, 'analyst1', 'old question', '2026-10-01T00:00:00Z')"
    )
    with engine.begin() as conn:
        conn.execute(text(sql), {"c": lead["case_id"]})
    locked = respond(auto_client, lead, "q-locked")
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "CASE_LOCKED"


@pytest.mark.ac("AC-13.4")
def test_ac13_4_close_sets_closed_and_cannot_repeat(client: TestClient) -> None:
    lead = create_lead(client)
    qid = raise_query(client, lead).json()["query_id"]
    first = close(client, lead, qid)
    assert first.status_code == 200 and first.json()["status"] == "CLOSED"
    again = close(client, lead, qid)
    assert again.status_code == 409 and again.json()["error"]["code"] == "QUERY_CLOSED"
    assert listing(client, lead).json()["items"][0]["status"] == "CLOSED"


@pytest.mark.nfr("NFR-02")
@pytest.mark.ac("AC-13.5")
@pytest.mark.parametrize("table", ["case_queries", "query_responses", "query_closures"])
def test_ac13_5_query_tables_are_append_only(
    client: TestClient, engine: Engine, table: str
) -> None:
    lead = create_lead(client)
    qid = raise_query(client, lead).json()["query_id"]
    respond(client, lead, qid)
    close(client, lead, qid)
    for statement in (f"UPDATE {table} SET created_at = 'x'", f"DELETE FROM {table}"):
        with pytest.raises(Exception, match="append-only"), engine.begin() as conn:
            conn.execute(text(statement))


@pytest.mark.nfr("NFR-03")
@pytest.mark.ac("AC-13.6")
def test_ac13_6_audit_holds_ids_only_and_logs_have_no_message_text(
    client: TestClient, engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    lead = create_lead(client)
    qid = raise_query(client, lead).json()["query_id"]
    respond(client, lead, qid)
    close(client, lead, qid)
    sql = "SELECT event, payload FROM audit_log WHERE event LIKE 'QUERY_%' ORDER BY seq"
    events = rows(engine, sql)
    assert [e[0] for e in events] == ["QUERY_RAISED", "QUERY_ANSWERED", "QUERY_CLOSED"]
    for _, payload in events:
        assert qid in payload and MESSAGE not in payload and REPLY not in payload
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert MESSAGE not in output and REPLY not in output


@pytest.mark.nfr("NFR-04")
@pytest.mark.ac("AC-13.7")
@pytest.mark.parametrize("user", ["prospect1", "officer1", "admin1"])
def test_ac13_7_only_analysts_raise_and_close(client: TestClient, user: str) -> None:
    lead = create_lead(client)
    qid = raise_query(client, lead).json()["query_id"]
    url = f"/api/v1/cases/{lead['case_id']}/queries"
    headers = staff_headers(client, user)
    body = {"message": "x"}
    assert client.post(url, json=body).status_code == 401
    assert client.post(url, json=body, headers=headers).status_code == 403
    assert client.post(f"{url}/{qid}/close", headers=headers).status_code == 403
    assert client.post(f"{url}/{qid}/responses", json=body, headers=headers).status_code == 403


@pytest.mark.nfr("NFR-04")
@pytest.mark.ac("AC-13.7")
def test_ac13_7_a_prospect_cannot_answer_another_cases_query(client: TestClient) -> None:
    lead = create_lead(client)
    other = create_lead(client, contact="9999999922")
    qid = raise_query(client, lead).json()["query_id"]
    stolen = client.post(
        f"/api/v1/cases/{lead['case_id']}/queries/{qid}/responses",
        json={"message": "x"},
        headers=bearer(other["access_token"]),
    )
    assert stolen.status_code == 403
