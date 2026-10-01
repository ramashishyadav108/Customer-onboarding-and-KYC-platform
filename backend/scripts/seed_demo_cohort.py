"""Deterministic synthetic demo cohort (200 cases) built through the real services.

Usage (from backend/, with DATABASE_URL and JWT_SECRET set as for run_backend.py):
    .venv/Scripts/python scripts/seed_demo_cohort.py [--count 200] [--force]

Fixed random seed and a deterministic clock starting 2026-09-01, so the reports are repeatable.
Only synthetic names are used (data-models section 5); no real PII exists anywhere.
"""

import argparse
import random
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text

from onboardx.config.settings import Settings, load_settings
from onboardx.controllers.dependencies.services import Services, build_services
from onboardx.repositories.database import (
    create_db_engine,
    create_session_factory,
    upgrade_to_head,
)
from onboardx.repositories.unit_of_work import make_uow_factory

SEED = 20261001
START = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
ACTOR = "seed"
CONTENT = b"%PDF-1.4 synthetic fixture"
CONTENT_TYPES = {"pdf": "application/pdf", "jpg": "image/jpeg", "png": "image/png"}
ID_PAN = "pan_valid.pdf"
BILL = "utility-bill_valid.pdf"
PHOTO = "photograph_valid.jpg"
GOOD_FILES: dict[str, dict[str, str]] = {
    "Savings": {"ID_PROOF": ID_PAN, "ADDRESS_PROOF": BILL, "PHOTOGRAPH": PHOTO},
    "Current": {
        "ID_PROOF": ID_PAN,
        "ADDRESS_PROOF": BILL,
        "PHOTOGRAPH": PHOTO,
        "BUSINESS_PROOF": "gst-certificate_valid.pdf",
    },
    "NRE": {
        "ID_PROOF": "passport_valid.png",
        "ADDRESS_PROOF": "aadhaar_valid.jpg",
        "PHOTOGRAPH": PHOTO,
        "OVERSEAS_ADDRESS_PROOF": "visa_valid.pdf",
    },
}
PROFILE_LOW = {
    "date_of_birth": "1990-04-12",
    "annual_income": 3000000,
    "occupation_category": "SELF_EMPLOYED",
    "country_code": "IN",
    "state_code": "MH",
}
PROFILE_MEDIUM = {
    "date_of_birth": "1960-03-01",
    "annual_income": 12000000,
    "occupation_category": "BUSINESS_OWNER",
    "country_code": "GB",
    "state_code": None,
}
PROFILE_HIGH = {
    "date_of_birth": "1960-03-01",
    "annual_income": 12000000,
    "occupation_category": "CASH_INTENSIVE",
    "country_code": "KP",
    "state_code": None,
}
WATCHLIST_NAMES = ["Test Person One", "Sample Launderer Alpha", "Mock Minister Epsilon",
                   "Example Senator Zeta", "Demo Racketeer Delta"]  # fmt: skip
PRODUCTS = ("Savings", "Current", "NRE")
REJECT_REASONS = ("CONFIRMED_WATCHLIST_MATCH", "DOCS_INSUFFICIENT", "RISK_TOO_HIGH", "POLICY_OTHER")
APPROVE_REASONS = ("FALSE_POSITIVE_CLEARED", "RISK_ACCEPTED", "DOCS_CONFIRMED")


class SeedClock:
    """Deterministic clock advanced explicitly by the seeder."""

    def __init__(self) -> None:
        self._now = START

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: int) -> None:
        self._now += timedelta(seconds=seconds)


def plan(count: int, rng: random.Random) -> list[str]:
    """Scenario per case: ~67% clean, the rest hits, MEDIUM and HIGH risk (shuffled)."""
    clean = count * 67 // 100
    rest = count - clean
    hits, medium = rest * 40 // 100, rest * 40 // 100
    kinds = ["CLEAN"] * clean + ["AML"] * hits + ["MEDIUM"] * medium
    kinds += ["HIGH"] * (count - len(kinds))
    rng.shuffle(kinds)
    return kinds


def case_spec(kind: str, index: int, rng: random.Random) -> tuple[str, str, dict[str, Any]]:
    """(name, product, profile) of one scenario."""
    if kind == "AML":
        return WATCHLIST_NAMES[index % len(WATCHLIST_NAMES)], rng.choice(PRODUCTS), PROFILE_LOW
    name = f"Synthetic Applicant {index + 1:03d}"
    if kind == "MEDIUM":
        return name, "Current", PROFILE_MEDIUM
    if kind == "HIGH":
        return name, "NRE", PROFILE_HIGH
    return name, rng.choice(PRODUCTS), PROFILE_LOW


def create_case(
    services: Services, clock: SeedClock, rng: random.Random, kind: str, index: int
) -> str:
    """Register, fill the profile, upload every mandatory document and submit (auto-advance)."""
    name, product, profile = case_spec(kind, index, rng)
    lead = services.leads.register(name=name, contact=f"90000{index:05d}", product=product)
    clock.advance(rng.randint(30, 900))
    services.leads.update_profile(case_id=lead.case_id, actor=ACTOR, **_profile_args(profile))
    for item, filename in GOOD_FILES[product].items():
        clock.advance(rng.randint(10, 600))
        services.documents.upload(
            case_id=lead.case_id, actor=ACTOR, checklist_item=item, filename=filename,
            content_type=CONTENT_TYPES[filename.rsplit(".", 1)[-1]], content=CONTENT,
        )  # fmt: skip
    clock.advance(rng.randint(30, 1800))
    services.submission.submit(case_id=lead.case_id, actor=ACTOR)
    return lead.case_id


def _profile_args(profile: dict[str, Any]) -> dict[str, Any]:
    from datetime import date

    args = dict(profile)
    args["date_of_birth"] = date.fromisoformat(args["date_of_birth"])
    return args


def resolve(services: Services, clock: SeedClock, rng: random.Random, case_id: str) -> None:
    """Resolve roughly 60% of the reviewed cases; the rest stay in the queue (backlog)."""
    roll = rng.randint(1, 100)
    if roll > 60:
        return
    clock.advance(rng.randint(600, 86400))
    approve = roll <= 20
    reasons = APPROVE_REASONS if approve else REJECT_REASONS
    services.overrides.override(
        case_id=case_id, decision="APPROVE" if approve else "REJECT",
        reason_code=rng.choice(reasons), comment=None, actor="officer1", role="compliance-officer",
    )  # fmt: skip


def seed(settings: Settings, count: int = 200, force: bool = False) -> dict[str, int]:
    """Populate the configured database; returns counts by final state."""
    engine = create_db_engine(settings.database_url)
    upgrade_to_head(engine)
    with engine.connect() as conn:
        existing = int(conn.execute(text("SELECT COUNT(*) FROM cases")).scalar_one())
    if existing and not force:
        raise SystemExit(f"database already holds {existing} cases; use --force to add more")
    factory = make_uow_factory(create_session_factory(engine))
    clock = SeedClock()
    secret = settings.jwt_secret or secrets.token_urlsafe(32)
    services = build_services(settings, factory, clock, secret)
    rng = random.Random(SEED)  # noqa: S311 - deterministic synthetic data, not security
    for index, kind in enumerate(plan(count, rng)):
        case_id = create_case(services, clock, rng, kind, index)
        if kind != "CLEAN":
            resolve(services, clock, rng, case_id)
        clock.advance(rng.randint(60, 3600))
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT state, COUNT(*) FROM cases GROUP BY state"))
        summary = {str(state): int(n) for state, n in rows}
    engine.dispose()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    summary = seed(load_settings(), args.count, args.force)
    print("seeded cases by state:", dict(sorted(summary.items())))  # noqa: T201
    print("uploads:", Path(load_settings().upload_dir).resolve())  # noqa: T201


if __name__ == "__main__":
    main()
