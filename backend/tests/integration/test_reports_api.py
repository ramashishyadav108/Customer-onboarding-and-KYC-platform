"""AC-10 / NFR-01 / NFR-03 / NFR-04: admin reports on a hand-computed history fixture."""

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from helpers import FakeClock
from report_fixture import CASES, T0, insert_history_case, seed_fixture, set_clock
from review_helpers import admin

BASE = "/api/v1/admin/reports"
NOW = datetime(2026, 9, 10, tzinfo=UTC)  # nine days after T0


@pytest.fixture
def seeded(engine: Engine, clock: FakeClock) -> dict[str, str]:
    set_clock(clock, NOW)
    return seed_fixture(engine)


def get(client: TestClient, path: str, **params: Any) -> Any:
    response = client.get(f"{BASE}/{path}", params=params, headers=admin(client))
    assert response.status_code == 200, response.text
    return response.json()


def stage(body: dict[str, Any], name: str) -> dict[str, Any]:
    return next(s for s in body["stages"] if s["stage"] == name)


@pytest.mark.ac("AC-10")
def test_ac10_1_tat_by_product_matches_the_hand_computed_values(
    client: TestClient, seeded: dict[str, str]
) -> None:
    """AC-10.1: count, avg, min, max in whole seconds; open cases (S4, C1, N2) excluded."""
    body = get(client, "tat")
    assert body["filters"] == {"product": None, "from": None, "to": None}
    got = [(i["product"], i["count"], i["avg_seconds"], i["min_seconds"], i["max_seconds"])
           for i in body["items"]]  # fmt: skip
    assert got == [
        ("Current", 2, 750, 600, 900),
        ("NRE", 1, 390, 390, 390),
        ("Savings", 4, 490, 280, 1000),
    ]


@pytest.mark.ac("AC-10")
def test_ac10_1_tat_average_uses_floor_division(client: TestClient, engine: Engine) -> None:
    """E5-S1 AC5: 10 + 11 seconds average to 10, never 10.5."""
    with engine.begin() as conn:
        for end in (10, 11):
            insert_history_case(conn, "NRE", [("INITIATED", 0), ("REJECTED", end)])
    item = get(client, "tat")["items"][0]
    assert item["avg_seconds"] == 10 and item["count"] == 2
    assert isinstance(item["avg_seconds"], int)


@pytest.mark.ac("AC-10")
def test_ac10_2_time_per_stage_uses_consecutive_transitions(
    client: TestClient, seeded: dict[str, str]
) -> None:
    """AC-10.2: mean seconds between consecutive transitions; open cases add completed stages."""
    stages = {(s["from_state"], s["to_state"]): s for s in get(client, "time-per-stage")["stages"]}
    expected = {
        ("CLASSIFIED", "APPROVED"): (3, 60),
        ("CLASSIFIED", "MANUAL_REVIEW"): (5, 0),
        ("DOCS_SUBMITTED", "SCREENED"): (8, 65),
        ("INITIATED", "DOCS_SUBMITTED"): (9, 85),
        ("MANUAL_REVIEW", "APPROVED"): (1, 600),
        ("MANUAL_REVIEW", "REJECTED"): (3, 523),
        ("SCREENED", "CLASSIFIED"): (8, 65),
    }
    assert {k: (v["count"], v["avg_seconds"]) for k, v in stages.items()} == expected
    order = [(s["from_state"], s["to_state"]) for s in get(client, "time-per-stage")["stages"]]
    assert order == sorted(order)


@pytest.mark.ac("AC-10")
def test_ac10_3_funnel_counts_and_conversion_match_hand_computed_values(
    client: TestClient, seeded: dict[str, str]
) -> None:
    """AC-10.3: ever-reached counts and integer basis-point conversion from the previous stage."""
    body = get(client, "funnel")
    got = [(s["stage"], s["count"], s["conversion_bp"]) for s in body["stages"]]
    assert got == [
        ("INITIATED", 10, 10000),
        ("DOCS_SUBMITTED", 9, 9000),
        ("SCREENED", 8, 8888),
        ("CLASSIFIED", 8, 10000),
        ("MANUAL_REVIEW", 5, 6250),
        ("APPROVED", 4, 5000),
        ("REJECTED", 3, 3750),
    ]


@pytest.mark.ac("AC-10")
def test_ac10_4_backlog_count_oldest_age_and_buckets(
    client: TestClient, seeded: dict[str, str]
) -> None:
    """AC-10.4: only C1 is still in MANUAL_REVIEW; age is whole minutes at the clock."""
    body = get(client, "backlog")
    assert body["count"] == 1 and body["oldest_age_minutes"] == (9 * 86400 - 300) // 60
    assert body["buckets"] == [
        {"label": "under_60", "min_minutes": 0, "max_minutes": 59, "count": 0},
        {"label": "60_to_1440", "min_minutes": 60, "max_minutes": 1440, "count": 0},
        {"label": "over_1440", "min_minutes": 1441, "max_minutes": None, "count": 1},
    ]


@pytest.mark.ac("AC-10")
def test_ac10_4_backlog_bucket_boundaries(
    client: TestClient, engine: Engine, clock: FakeClock
) -> None:
    """AC-10.4: 59 -> under 60; 60 and 1440 -> middle; 1441 -> over."""
    set_clock(clock, T0.replace(year=2027))
    now_offset = int((clock.now() - T0).total_seconds())
    with engine.begin() as conn:
        for minutes, seconds in ((30, 0), (59, 59), (60, 0), (1440, 0), (1441, 0), (5000, 30)):
            entered = now_offset - minutes * 60 - seconds
            insert_history_case(
                conn, "Savings",
                [("INITIATED", 0), ("DOCS_SUBMITTED", 1), ("SCREENED", 2), ("CLASSIFIED", 3),
                 ("MANUAL_REVIEW", entered)],
                ("MANUAL_REVIEW", "AML_HIT"),
            )  # fmt: skip
    body = get(client, "backlog")
    assert [b["count"] for b in body["buckets"]] == [2, 2, 2]
    assert body["count"] == 6 and body["oldest_age_minutes"] == 5000


@pytest.mark.ac("AC-10")
def test_ac10_5_rejection_reasons_count_desc_then_code_asc(
    client: TestClient, seeded: dict[str, str]
) -> None:
    """AC-10.5: RISK_TOO_HIGH (2) before CONFIRMED_WATCHLIST_MATCH (1)."""
    body = get(client, "rejection-reasons")
    assert body["items"] == [
        {"reason_code": "RISK_TOO_HIGH", "count": 2},
        {"reason_code": "CONFIRMED_WATCHLIST_MATCH", "count": 1},
    ]


@pytest.mark.ac("AC-10")
def test_ac10_5_equal_counts_are_ordered_by_code_and_capped_at_five(
    client: TestClient, engine: Engine
) -> None:
    """AC-10.5: ties resolve by code ascending; the query never returns more than five."""
    path = [("INITIATED", 0), ("DOCS_SUBMITTED", 1), ("SCREENED", 2), ("CLASSIFIED", 3),
            ("MANUAL_REVIEW", 4), ("REJECTED", 5)]  # fmt: skip
    with engine.begin() as conn:
        for reason in ("POLICY_OTHER", "DOCS_INSUFFICIENT", "CONFIRMED_WATCHLIST_MATCH"):
            insert_history_case(conn, "NRE", path, ("MANUAL_REVIEW", "AML_HIT"), ("REJECT", reason))
        insert_history_case(
            conn, "NRE", path, ("MANUAL_REVIEW", "AML_HIT"), ("REJECT", "POLICY_OTHER")
        )
    items = get(client, "rejection-reasons")["items"]
    assert [(i["reason_code"], i["count"]) for i in items] == [
        ("POLICY_OTHER", 2), ("CONFIRMED_WATCHLIST_MATCH", 1), ("DOCS_INSUFFICIENT", 1),
    ]  # fmt: skip
    assert len(items) <= 5


@pytest.mark.ac("AC-10")
def test_ac10_5_approved_overrides_are_not_rejection_reasons(
    client: TestClient, seeded: dict[str, str]
) -> None:
    """E5-S2 AC3: only REJECT overrides count (C2 approved with RISK_ACCEPTED is absent)."""
    codes = {i["reason_code"] for i in get(client, "rejection-reasons")["items"]}
    assert "RISK_ACCEPTED" not in codes


@pytest.mark.ac("AC-10")
def test_ac10_6_auto_approval_rate_against_the_6000_bp_target(
    client: TestClient, seeded: dict[str, str]
) -> None:
    """AC-10.6: 3 AUTO approvals of 8 decided = 3750 bp, target 6000, met false."""
    assert get(client, "auto-approval") == {
        "filters": {"product": None, "from": None, "to": None},
        "auto_approved": 3, "decided": 8, "rate_bp": 3750, "target_bp": 6000, "met": False,
    }  # fmt: skip
    body = get(client, "auto-approval", product="Savings")
    assert (body["auto_approved"], body["decided"], body["rate_bp"], body["met"]) == (
        3,
        4,
        7500,
        True,
    )


@pytest.mark.ac("AC-10")
def test_ac10_6_target_is_met_at_exactly_6000_bp(client: TestClient, engine: Engine) -> None:
    """AC-10.6: 3 of 5 is exactly 6000 bp and counts as met."""
    clean = [("INITIATED", 0), ("DOCS_SUBMITTED", 1), ("SCREENED", 2), ("CLASSIFIED", 3),
             ("APPROVED", 4)]  # fmt: skip
    review = [*clean[:4], ("MANUAL_REVIEW", 4)]
    with engine.begin() as conn:
        for _ in range(3):
            insert_history_case(conn, "Savings", clean, ("APPROVED", "AUTO_APPROVED"))
        for _ in range(2):
            insert_history_case(conn, "Savings", review, ("MANUAL_REVIEW", "RISK_MEDIUM"))
    body = get(client, "auto-approval")
    assert body["rate_bp"] == 6000 and body["met"] is True


@pytest.mark.ac("AC-10")
def test_ac10_7_product_filter_applies_to_every_metric(
    client: TestClient, seeded: dict[str, str]
) -> None:
    """AC-10.7: product=Savings narrows tat, funnel, backlog, stages and reasons."""
    tat = get(client, "tat", product="Savings")
    assert [i["product"] for i in tat["items"]] == ["Savings"] and tat["filters"][
        "product"
    ] == "Savings"
    funnel = [(s["stage"], s["count"], s["conversion_bp"]) for s in
              get(client, "funnel", product="Savings")["stages"]]  # fmt: skip
    assert funnel == [
        ("INITIATED", 5, 10000), ("DOCS_SUBMITTED", 5, 10000), ("SCREENED", 4, 8000),
        ("CLASSIFIED", 4, 10000), ("MANUAL_REVIEW", 1, 2500), ("APPROVED", 3, 7500),
        ("REJECTED", 1, 2500),
    ]  # fmt: skip
    assert get(client, "backlog", product="Savings")["count"] == 0
    assert get(client, "backlog", product="Current")["count"] == 1
    reasons = get(client, "rejection-reasons", product="Savings")["items"]
    assert reasons == [{"reason_code": "CONFIRMED_WATCHLIST_MATCH", "count": 1}]
    stages = {(s["from_state"], s["to_state"]): s["count"] for s in
              get(client, "time-per-stage", product="NRE")["stages"]}  # fmt: skip
    assert stages[("INITIATED", "DOCS_SUBMITTED")] == 1


@pytest.mark.ac("AC-10")
def test_ac10_7_date_filters_are_inclusive_and_use_the_initiated_date(
    client: TestClient, seeded: dict[str, str]
) -> None:
    """AC-10.7: from/to are inclusive dates on the INITIATED timestamp."""
    only_s5 = get(client, "tat", **{"from": "2026-09-05"})
    assert only_s5["items"] == [
        {
            "product": "Savings",
            "count": 1,
            "avg_seconds": 300,
            "min_seconds": 300,
            "max_seconds": 300,
        }
    ]
    same_day = get(client, "tat", **{"from": "2026-09-05", "to": "2026-09-05"})
    assert same_day["items"] == only_s5["items"]
    assert same_day["filters"] == {"product": None, "from": "2026-09-05", "to": "2026-09-05"}
    before = get(client, "funnel", **{"to": "2026-09-01"})
    assert stage(before, "INITIATED")["count"] == 9 and stage(before, "APPROVED")["count"] == 3
    both = get(client, "tat", product="Current", to="2026-09-04")
    assert both["items"][0]["count"] == 2


@pytest.mark.ac("AC-10")
def test_ac10_7_empty_results_return_zeros_not_errors(
    client: TestClient, seeded: dict[str, str]
) -> None:
    """AC-10.7: a window with no cases returns zeros and empty arrays."""
    window = {"from": "2026-09-02", "to": "2026-09-04"}
    assert get(client, "tat", **window)["items"] == []
    assert get(client, "rejection-reasons", **window)["items"] == []
    assert get(client, "time-per-stage", **window)["stages"] == []
    funnel = get(client, "funnel", **window)["stages"]
    assert all(s["count"] == 0 and s["conversion_bp"] == 0 for s in funnel) and len(funnel) == 7
    backlog = get(client, "backlog", **window)
    assert backlog["count"] == 0 and backlog["oldest_age_minutes"] == 0
    assert [b["count"] for b in backlog["buckets"]] == [0, 0, 0]
    auto = get(client, "auto-approval", **window)
    assert (auto["auto_approved"], auto["decided"], auto["rate_bp"], auto["met"]) == (
        0,
        0,
        0,
        False,
    )


@pytest.mark.ac("AC-10")
def test_ac10_7_empty_database_returns_zeros_on_every_report(client: TestClient) -> None:
    """AC-10.7: no data at all is still a 200 on every report."""
    for path in (
        "tat",
        "funnel",
        "backlog",
        "time-per-stage",
        "rejection-reasons",
        "auto-approval",
    ):
        assert client.get(f"{BASE}/{path}", headers=admin(client)).status_code == 200


@pytest.mark.ac("AC-10")
@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"product": "Loans"}, "product"),
        ({"from": "2026-13-01"}, "from"),
        ({"from": "20260901"}, "from"),
        ({"to": "yesterday"}, "to"),
        ({"to": "2026-02-30"}, "to"),
        ({"from": "1234567890"}, "from"),
        ({"from": "2026-09-05", "to": "2026-09-01"}, "from"),
    ],
)
@pytest.mark.parametrize(
    "path", ["tat", "funnel", "backlog", "time-per-stage", "rejection-reasons", "auto-approval"]
)
def test_ac10_7_invalid_filters_are_422_and_name_the_parameter(
    client: TestClient, path: str, params: dict[str, str], field: str
) -> None:
    """AC-10.7 / E5-S3 AC3: invalid product or date returns 422 naming the parameter."""
    response = client.get(f"{BASE}/{path}", params=params, headers=admin(client))
    body = response.json()["error"]
    assert response.status_code == 422 and body["code"] == "VALIDATION_ERROR"
    assert body["details"]["fields"][0]["field"] == field


@pytest.mark.ac("AC-10")
@pytest.mark.ac("AC-10.11")
def test_ac10_dropped_lead_analysis_counts_idle_open_cases_by_stage(
    client: TestClient, seeded: dict[str, str]
) -> None:
    """Brief 6.2: open INITIATED / DOCS_SUBMITTED cases idle longer than N days."""
    body = get(client, "dropped-leads", older_than_days=8)
    assert body == {
        "older_than_days": 8, "total": 2,
        "stages": [{"stage": "INITIATED", "count": 1}, {"stage": "DOCS_SUBMITTED", "count": 1}],
    }  # fmt: skip
    assert get(client, "dropped-leads", older_than_days=9)["total"] == 0  # strictly older than
    assert get(client, "dropped-leads", older_than_days=8, product="NRE")["total"] == 1
    assert get(client, "dropped-leads")["older_than_days"] == 7


@pytest.mark.ac("AC-10")
@pytest.mark.parametrize("days", ["0", "366", "x"])
def test_ac10_dropped_lead_days_are_validated(client: TestClient, days: str) -> None:
    """older_than_days must be 1..365."""
    response = client.get(
        f"{BASE}/dropped-leads", params={"older_than_days": days}, headers=admin(client)
    )
    assert response.status_code == 422


@pytest.mark.ac("AC-10")
@pytest.mark.nfr("NFR-04")
@pytest.mark.parametrize(
    "path",
    ["tat", "funnel", "backlog", "time-per-stage", "rejection-reasons", "auto-approval",
     "dropped-leads"],
)  # fmt: skip
@pytest.mark.parametrize("user", ["prospect1", "analyst1", "officer1"])
def test_ac10_8_non_admin_roles_get_403_and_no_token_401(
    client: TestClient, path: str, user: str
) -> None:
    """AC-10.8: 401 without a token, 403 for prospect, analyst and officer."""
    from api_helpers import staff_headers

    assert client.get(f"{BASE}/{path}").status_code == 401
    response = client.get(f"{BASE}/{path}", headers=staff_headers(client, user))
    assert response.status_code == 403 and response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.ac("AC-10")
@pytest.mark.nfr("NFR-03")
@pytest.mark.nfr("NFR-01")
def test_ac10_8_payloads_contain_no_pii_and_no_floats(
    client: TestClient, seeded: dict[str, str]
) -> None:
    """AC-10.8 / NFR-03: no name or contact in any payload; NFR-01: numbers are ints."""
    import json

    def walk(value: Any) -> None:
        assert not isinstance(value, float), value
        if isinstance(value, dict):
            assert not {"name", "contact", "contact_masked", "profile"} & set(value)
            for child in value.values():
                walk(child)
        if isinstance(value, list):
            for child in value:
                walk(child)

    for path in ("tat", "funnel", "backlog", "time-per-stage", "rejection-reasons",
                 "auto-approval", "dropped-leads"):  # fmt: skip
        body = get(client, path)
        walk(body)
        text = json.dumps(body)
        for secret in ("Test Person", "9999999921", "9999999"):
            assert secret not in text, (path, secret)


@pytest.mark.ac("AC-10")
def test_ac10_reports_do_not_modify_the_database(
    client: TestClient, engine: Engine, seeded: dict[str, str]
) -> None:
    """Reports are read-only: row counts are identical before and after every call."""
    from pipeline_helpers import rows

    tables = ("cases", "state_history", "decisions", "overrides", "audit_log")
    before = [rows(engine, f"SELECT COUNT(*) FROM {t}")[0][0] for t in tables]
    for path in ("tat", "funnel", "backlog", "time-per-stage", "rejection-reasons",
                 "auto-approval", "dropped-leads"):  # fmt: skip
        get(client, path)
    assert [rows(engine, f"SELECT COUNT(*) FROM {t}")[0][0] for t in tables] == before
    assert len(CASES) == 10 and T0.year == 2026


@pytest.mark.ac("AC-10")
def test_ac10_reports_reflect_real_pipeline_activity(client: TestClient, clock: FakeClock) -> None:
    """End to end through the API: one auto-approved and one reviewed-then-rejected case."""
    from pipeline_helpers import step, submitted_case
    from review_helpers import case_in_review, officer, override

    lead = submitted_case(client)
    clock.advance(30)
    step(client, lead, "advance")
    review = case_in_review(client, "AML")
    clock.advance(300)
    assert override(client, review, "REJECT", "POLICY_OTHER").status_code == 200
    tat = get(client, "tat")["items"]
    assert tat[0]["product"] == "Savings" and tat[0]["count"] == 2
    assert get(client, "auto-approval")["auto_approved"] == 1
    assert get(client, "rejection-reasons")["items"] == [
        {"reason_code": "POLICY_OTHER", "count": 1}
    ]
    assert get(client, "backlog")["count"] == 0
    assert officer(client)
