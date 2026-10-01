"""AC-10.6 / NFR-03: the deterministic 200-case demo cohort and its report values."""

import importlib.util
import json
import shutil
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from helpers import JWT_SECRET, sqlite_url
from onboardx.config.settings import Settings
from onboardx.main import create_app
from review_helpers import admin

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "seed_demo_cohort.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("seed_demo_cohort", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def settings_for(path: Path, uploads: Path) -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None, database_url=sqlite_url(path), jwt_secret=JWT_SECRET, upload_dir=uploads
    )


@pytest.fixture(scope="module")
def cohort(tmp_path_factory: pytest.TempPathFactory, migrated_template: Path) -> Settings:
    root = tmp_path_factory.mktemp("cohort")
    shutil.copy(migrated_template, root / "demo.db")
    settings = settings_for(root / "demo.db", root / "uploads")
    load_script().seed(settings, 200)
    return settings


@pytest.mark.ac("AC-10")
def test_ac10_6_cohort_has_200_cases_and_at_least_60_percent_auto_approved(
    cohort: Settings,
) -> None:
    """AC-10.6: 200 cases, auto-approval rate >= 6000 bp, target met."""
    with TestClient(create_app(cohort)) as client:
        headers = admin(client)
        auto = client.get("/api/v1/admin/reports/auto-approval", headers=headers).json()
        funnel = client.get("/api/v1/admin/reports/funnel", headers=headers).json()
    assert auto["decided"] == 200 and auto["auto_approved"] >= 120
    assert auto["rate_bp"] >= 6000 and auto["met"] is True
    assert funnel["stages"][0]["count"] == 200


@pytest.mark.ac("AC-10")
def test_ac10_cohort_populates_every_report(cohort: Settings) -> None:
    """The demo cohort yields data in tat, backlog, stages and rejection reasons."""
    with TestClient(create_app(cohort)) as client:
        headers = admin(client)

        def get(path: str) -> dict[str, object]:
            response = client.get(f"/api/v1/admin/reports/{path}", headers=headers)
            assert response.status_code == 200
            body: dict[str, object] = response.json()
            return body

        assert get("tat")["items"]
        assert get("time-per-stage")["stages"]
        assert get("rejection-reasons")["items"]
        assert int(str(get("backlog")["count"])) > 0
        body = json.dumps([get("tat"), get("funnel")])
    assert "Synthetic Applicant" not in body


@pytest.mark.ac("AC-10")
def test_ac10_cohort_cases_cover_every_scenario(cohort: Settings) -> None:
    """AML hits, MEDIUM and HIGH risk, approvals and rejections all occur."""
    from onboardx.repositories.database import create_db_engine

    engine: Engine = create_db_engine(cohort.database_url)
    with engine.connect() as conn:
        reasons = {
            str(r[0]) for r in conn.execute(text("SELECT DISTINCT reason_code FROM decisions"))
        }
        states = {str(r[0]) for r in conn.execute(text("SELECT DISTINCT state FROM cases"))}
        accounts = conn.execute(text("SELECT COUNT(*) FROM accounts")).scalar_one()
    engine.dispose()
    assert {"AUTO_APPROVED", "AML_HIT", "RISK_MEDIUM", "RISK_HIGH"} <= reasons
    assert {"APPROVED", "REJECTED", "MANUAL_REVIEW"} <= states and accounts >= 120


@pytest.mark.ac("AC-10")
def test_ac10_seed_is_deterministic_and_refuses_a_non_empty_database(
    tmp_path: Path, migrated_template: Path
) -> None:
    """Same seed gives identical state counts; a second run without --force exits."""
    script = load_script()
    results = []
    for name in ("a", "b"):
        shutil.copy(migrated_template, tmp_path / f"{name}.db")
        results.append(script.seed(settings_for(tmp_path / f"{name}.db", tmp_path / name), 20))
    assert results[0] == results[1] and sum(results[0].values()) == 20
    with pytest.raises(SystemExit):
        script.seed(settings_for(tmp_path / "a.db", tmp_path / "a"), 5)
