"""NFR-05 / E1-S2 AC2 / E1-S5 / E3-S2 AC6: seed migrations 0003-0007 on an empty database."""

import json
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, text

from api_helpers import DEMO_PASSWORDS
from helpers import sqlite_url
from onboardx.config.constants import ALEMBIC_INI, MIGRATIONS_DIR
from onboardx.repositories.database import upgrade_to_head
from onboardx.services.passwords import verify_password
from ruleset_fixture import V1_DICT


def rows(engine: Engine, sql: str) -> list[Any]:
    with engine.connect() as conn:
        return list(conn.execute(text(sql)).all())


@pytest.mark.nfr("NFR-05")
def test_nfr05_single_linear_history_ends_at_0008() -> None:
    """NFR-05: eight migrations, one head, in the documented order."""
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["0008"]
    revisions = [r.revision for r in script.walk_revisions()]
    assert revisions == ["0008", "0007", "0006", "0005", "0004", "0003", "0002", "0001"]


@pytest.mark.nfr("NFR-05")
def test_nfr05_migration_files_are_named_as_documented() -> None:
    """NFR-05: the migration file names match folder-structure.md."""
    names = sorted(p.name for p in (MIGRATIONS_DIR / "versions").glob("0*.py"))
    assert names == [
        "0001_core_schema.py",
        "0002_append_only_triggers.py",
        "0003_seed_users.py",
        "0004_seed_checklists_v1.py",
        "0005_seed_classification_rules_v1.py",
        "0006_seed_rule_set_v1.py",
        "0007_seed_watchlist_v1.py",
        "0008_admin_users_checklists_queries.py",
    ]


@pytest.mark.nfr("NFR-04")
def test_nfr04_exactly_one_seeded_user_per_role(engine: Engine) -> None:
    """E1-S2 AC2: one synthetic user each for the four roles."""
    users = rows(engine, "SELECT username, role FROM users ORDER BY username")
    assert [tuple(u) for u in users] == [
        ("admin1", "admin"),
        ("analyst1", "kyc-analyst"),
        ("officer1", "compliance-officer"),
        ("prospect1", "prospect"),
    ]


@pytest.mark.nfr("NFR-04")
def test_nfr04_seed_passwords_are_salted_hashes_and_verify(engine: Engine) -> None:
    """E1-S2 AC2: only salted PBKDF2 hashes are stored; per-user salts differ."""
    stored = {r[0]: r[1] for r in rows(engine, "SELECT username, password_hash FROM users")}
    salts = set()
    for username, password in DEMO_PASSWORDS.items():
        value = stored[username]
        algorithm, iterations, salt, digest = value.split("$")
        assert algorithm == "pbkdf2_sha256" and int(iterations) >= 100_000
        assert password not in value
        assert verify_password(password, value)
        salts.add(salt)
    assert len(salts) == 4


@pytest.mark.ac("AC-02")
def test_ac02_1_savings_checklist_v1_seed(engine: Engine) -> None:
    """AC-02.1 / E1-S5 AC1: Savings has three mandatory items with their accepted classes."""
    items = rows(
        engine,
        "SELECT item_code, mandatory, accepted_classes FROM checklist_items"
        " WHERE product='Savings' AND version=1 ORDER BY item_code",
    )
    assert {i[0]: (i[1], json.loads(i[2])) for i in items} == {
        "ID_PROOF": (1, ["PAN", "AADHAAR", "PASSPORT"]),
        "ADDRESS_PROOF": (1, ["AADHAAR", "PASSPORT", "UTILITY_BILL"]),
        "PHOTOGRAPH": (1, ["PHOTOGRAPH"]),
    }


@pytest.mark.ac("AC-02")
def test_ac02_2_3_current_and_nre_checklist_seed(engine: Engine) -> None:
    """AC-02.2/02.3: Current adds BUSINESS_PROOF; NRE has PASSPORT-only ID and OVERSEAS proof."""
    sql = "SELECT item_code, accepted_classes FROM checklist_items WHERE product='{}' AND version=1"
    current = {r[0]: json.loads(r[1]) for r in rows(engine, sql.format("Current"))}
    nre = {r[0]: json.loads(r[1]) for r in rows(engine, sql.format("NRE"))}
    assert set(current) == {"ID_PROOF", "ADDRESS_PROOF", "PHOTOGRAPH", "BUSINESS_PROOF"}
    assert current["BUSINESS_PROOF"] == ["GST_CERTIFICATE"]
    assert set(nre) == {"ID_PROOF", "ADDRESS_PROOF", "PHOTOGRAPH", "OVERSEAS_ADDRESS_PROOF"}
    assert nre["ID_PROOF"] == ["PASSPORT"]
    assert nre["OVERSEAS_ADDRESS_PROOF"] == ["VISA"]


@pytest.mark.ac("AC-06")
def test_ac06_6_seeded_rule_set_v1_matches_spec(engine: Engine) -> None:
    """AC-06.6: published v1 equals the spec values, including border_states JK, PB, AS."""
    (row,) = rows(engine, "SELECT * FROM risk_rule_sets")
    data = row._mapping
    assert data["version"] == 1 and data["status"] == "PUBLISHED"
    assert data["published_at"] is not None
    assert json.loads(data["weights"]) == V1_DICT["weights"]
    assert json.loads(data["points"]) == V1_DICT["points"]
    assert json.loads(data["geography_map"]) == V1_DICT["geography_map"]
    assert json.loads(data["border_states"]) == ["JK", "PB", "AS"]
    assert (data["low_max"], data["medium_max"]) == (29, 59)


@pytest.mark.ac("AC-03")
def test_ac03_7_classification_rules_v1_seed(engine: Engine) -> None:
    """AC-03.7: seven filename-prefix rules at 9500 bp, all VERIFIED."""
    rules = rows(
        engine, "SELECT prefix, doc_class, status, confidence_bp FROM classification_rules"
    )
    assert len(rules) == 7
    assert {r[0] for r in rules} == {
        "pan_", "aadhaar_", "passport_", "utility-bill_", "photograph_",
        "gst-certificate_", "visa_",
    }  # fmt: skip
    assert {(r[2], r[3]) for r in rules} == {("VERIFIED", 9500)}


@pytest.mark.ac("AC-05")
def test_ac05_8_watchlist_seed_has_five_aml_and_five_pep(engine: Engine) -> None:
    """AC-05.8: ten synthetic entries, five AML and five PEP, with normalised tokens."""
    counts = dict(rows(engine, "SELECT list_type, COUNT(*) FROM watchlist_entries GROUP BY 1"))
    assert counts == {"AML": 5, "PEP": 5}
    (tokens,) = rows(
        engine, "SELECT name_tokens FROM watchlist_entries WHERE name='Test Person One'"
    )
    assert tokens[0] == "one person test"


@pytest.mark.nfr("NFR-05")
def test_nfr05_upgrade_from_empty_database_creates_seeded_schema(tmp_path: Path) -> None:
    """NFR-05: a brand-new database upgraded to head holds every seed."""
    url = sqlite_url(tmp_path / "empty.db")
    upgrade_to_head(url)
    eng = create_engine(url)
    try:
        with eng.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            users = conn.execute(text("SELECT COUNT(*) FROM users")).scalar_one()
        assert (version, users) == ("0008", 4)
    finally:
        eng.dispose()
