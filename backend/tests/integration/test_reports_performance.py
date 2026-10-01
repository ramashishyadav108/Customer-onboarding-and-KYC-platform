"""AC-10.9 / E5-S3 AC4: every report answers in under 500 ms (p95) over 1,000 synthetic cases."""

import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from report_fixture import AUTO, insert_history_case
from review_helpers import admin

CASES = 1000
REPEATS = 20
LIMIT_SECONDS = 0.5
PATHS = ("tat", "funnel", "backlog", "time-per-stage", "rejection-reasons", "auto-approval")
CLEAN = [("INITIATED", 0), ("DOCS_SUBMITTED", 60), ("SCREENED", 120), ("CLASSIFIED", 180),
         ("APPROVED", 240)]  # fmt: skip
REVIEW = [*CLEAN[:4], ("MANUAL_REVIEW", 180)]
REJECTED = [*REVIEW, ("REJECTED", 900)]
OPEN = CLEAN[:2]


def populate(engine: Engine) -> None:
    products = ("Savings", "Current", "NRE")
    with engine.begin() as conn:
        for index in range(CASES):
            product = products[index % 3]
            kind = index % 10
            if kind < 6:
                insert_history_case(conn, product, CLEAN, AUTO)
            elif kind == 6:
                insert_history_case(conn, product, REVIEW, ("MANUAL_REVIEW", "RISK_MEDIUM"))
            elif kind in (7, 8):
                reject = ("REJECT", "RISK_TOO_HIGH" if index % 2 else "POLICY_OTHER")
                insert_history_case(conn, product, REJECTED, ("MANUAL_REVIEW", "AML_HIT"), reject)
            else:
                insert_history_case(conn, product, OPEN)


def p95(samples: list[float]) -> float:
    ordered = sorted(samples)
    return ordered[(len(ordered) * 95 + 99) // 100 - 1]


@pytest.mark.ac("AC-10")
@pytest.mark.parametrize("path", PATHS)
def test_ac10_9_p95_latency_is_under_500_ms_at_1000_cases(
    client: TestClient, engine: Engine, path: str
) -> None:
    """AC-10.9: each report endpoint, unfiltered, over a 1,000-case history."""
    populate(engine)
    headers = admin(client)
    url = f"/api/v1/admin/reports/{path}"
    assert client.get(url, headers=headers).status_code == 200  # warm up
    samples: list[float] = []
    for _ in range(REPEATS):
        started = time.perf_counter()
        response = client.get(url, headers=headers)
        samples.append(time.perf_counter() - started)
        assert response.status_code == 200
    assert p95(samples) < LIMIT_SECONDS, (path, p95(samples))


@pytest.mark.ac("AC-10")
def test_ac10_9_the_1000_case_fixture_has_the_expected_shape(
    client: TestClient, engine: Engine
) -> None:
    """Sanity: 1,000 cases; 600 auto-approved; 200 rejected; 100 in review; 100 open."""
    populate(engine)
    headers = admin(client)
    auto = client.get("/api/v1/admin/reports/auto-approval", headers=headers).json()
    assert (auto["auto_approved"], auto["decided"], auto["rate_bp"]) == (600, 900, 6666)
    body = client.get("/api/v1/admin/reports/funnel", headers=headers).json()
    funnel = {s["stage"]: s["count"] for s in body["stages"]}
    assert funnel["INITIATED"] == 1000 and funnel["REJECTED"] == 200
    assert client.get("/api/v1/admin/reports/backlog", headers=headers).json()["count"] == 100
