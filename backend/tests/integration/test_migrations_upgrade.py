"""E1-S1 AC5 / DD-14: alembic upgrade head on SQLite, schema shape, state_code column."""

from pathlib import Path

import pytest
from helpers import insert_case, sqlite_url
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from onboardx.repositories.database import create_db_engine, is_in_memory, upgrade_to_head

EXPECTED_TABLES = {
    "users",
    "cases",
    "case_profiles",
    "checklist_templates",
    "checklist_items",
    "documents",
    "document_rejections",
    "classification_rules",
    "classification_results",
    "screening_results",
    "watchlist_entries",
    "watchlist_deactivations",
    "risk_rule_sets",
    "risk_assessments",
    "decisions",
    "overrides",
    "accounts",
    "notifications",
    "state_history",
    "audit_log",
    "idempotency_keys",
}


def test_nfr05_upgrade_head_runs_clean_on_empty_sqlite(tmp_path: Path) -> None:
    """NFR-05 (E1-S1 AC5): alembic upgrade head succeeds on an empty SQLite database."""
    url = sqlite_url(tmp_path / "fresh.db")
    upgrade_to_head(url)
    eng = create_engine(url)
    try:
        assert EXPECTED_TABLES <= set(inspect(eng).get_table_names())
    finally:
        eng.dispose()


def test_nfr05_upgrade_head_is_idempotent(tmp_path: Path) -> None:
    """NFR-05: running upgrade head twice is a no-op, not an error."""
    url = sqlite_url(tmp_path / "twice.db")
    upgrade_to_head(url)
    upgrade_to_head(url)


def test_nfr05_in_memory_sqlite_shares_one_connection() -> None:
    """NFR-05: an in-memory SQLite engine keeps the migrated schema across sessions."""
    assert is_in_memory("sqlite://")
    assert is_in_memory("sqlite:///:memory:")
    assert not is_in_memory("sqlite:///./x.db")
    eng = create_db_engine("sqlite://")
    upgrade_to_head(eng)
    with eng.connect() as first:
        first.execute(text("SELECT 1 FROM cases"))
    with eng.connect() as second:
        assert "cases" in inspect(second).get_table_names()
    eng.dispose()


def test_nfr01_foreign_keys_are_enforced(engine: Engine) -> None:
    """Data model rule: SQLite PRAGMA foreign_keys is ON for every connection."""
    with engine.connect() as conn, pytest.raises(IntegrityError):
        conn.execute(
            text(
                "INSERT INTO cases (case_id, name, contact, product, state, checklist_version,"
                " created_at, updated_at) VALUES ('c1', 'n', 'c', 'Savings', 'INITIATED', 99,"
                " 't', 't')"
            )
        )


@pytest.mark.parametrize("state_code", [None, "PB", "MH"])
def test_ac01_profile_state_code_accepts_null_or_two_uppercase_letters(
    engine: Engine, state_code: str | None
) -> None:
    """AC-01 / DD-14: case_profiles.state_code is nullable, two uppercase letters when present."""
    with engine.begin() as conn:
        case_id = insert_case(conn)
        conn.execute(
            text(
                "INSERT INTO case_profiles (case_id, date_of_birth, annual_income,"
                " occupation_category, country_code, state_code, updated_at)"
                " VALUES (:id, '1990-04-12', 3000000, 'SELF_EMPLOYED', 'IN', :sc, 't')"
            ),
            {"id": case_id, "sc": state_code},
        )


@pytest.mark.parametrize("state_code", ["pb", "P", "PBX", "P1"])
def test_ac01_profile_state_code_rejects_malformed_values(engine: Engine, state_code: str) -> None:
    """AC-01 / DD-14: a malformed state_code violates the CHECK constraint."""
    with engine.begin() as conn:
        case_id = insert_case(conn)
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO case_profiles (case_id, date_of_birth, annual_income,"
                    " occupation_category, country_code, state_code, updated_at)"
                    " VALUES (:id, '1990-04-12', 3000000, 'SELF_EMPLOYED', 'IN', :sc, 't')"
                ),
                {"id": case_id, "sc": state_code},
            )


def test_nfr01_no_float_columns_in_schema(engine: Engine) -> None:
    """NFR-01: no float, real, double or numeric column exists anywhere in the schema."""
    inspector = inspect(engine)
    banned = ("FLOAT", "REAL", "DOUBLE", "NUMERIC", "DECIMAL")
    for table in inspector.get_table_names():
        for column in inspector.get_columns(table):
            assert not any(b in str(column["type"]).upper() for b in banned), (table, column)
