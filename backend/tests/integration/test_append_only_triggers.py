"""NFR-02 / NFR-05 / NFR-08 / E1-S4 AC5: database triggers reject UPDATE and DELETE."""

import inspect
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DatabaseError

from helpers import NOW, insert_case
from onboardx.repositories.audit_repository import AuditRepository
from onboardx.repositories.state_history_repository import StateHistoryRepository

CASE_SQL = {
    "state_history": (
        "INSERT INTO state_history (history_id, case_id, from_state, to_state, actor, created_at)"
        " VALUES ('h1', :c, NULL, 'INITIATED', 'a', :t)"
    ),
    "audit_log": (
        "INSERT INTO audit_log (audit_id, case_id, event, actor, role, payload, correlation_id,"
        " created_at) VALUES ('a1', :c, 'E', 'a', 'r', '{}', 'x', :t)"
    ),
    "screening_results": (
        "INSERT INTO screening_results (id, case_id, hits, requires_manual_review,"
        " watchlist_version, screened_at) VALUES ('s1', :c, '[]', 0, 10, :t)"
    ),
    "risk_assessments": (
        "INSERT INTO risk_assessments (assessment_id, case_id, score, band, rule_version, source,"
        " breakdown, created_at) VALUES ('r1', :c, 16, 'LOW', 1, 'RULE_ENGINE', '[]', :t)"
    ),
    "decisions": (
        "INSERT INTO decisions (decision_id, case_id, type, outcome, reason_code, rule_version,"
        " actor, created_at) VALUES ('d1', :c, 'AUTO', 'APPROVED', 'AUTO_APPROVED', 1, 'a', :t)"
    ),
    "documents": (
        "INSERT INTO documents (document_id, case_id, checklist_item, version, storage_path,"
        " display_name, content_type, size_bytes, sha256, uploaded_by, uploaded_at)"
        " VALUES ('doc1', :c, 'ID_PROOF', 1, 'p', 'pan_valid.pdf', 'application/pdf', 10,"
        " :h, 'a', :t)"
    ),
    "idempotency_keys": (
        "INSERT INTO idempotency_keys (key, scope, request_hash, response, created_at)"
        " VALUES ('k1', 'leads', :h, '{}', :t)"
    ),
}
UPDATES = {
    "state_history": "UPDATE state_history SET actor = 'x'",
    "audit_log": "UPDATE audit_log SET actor = 'x'",
    "screening_results": "UPDATE screening_results SET watchlist_version = 11",
    "risk_assessments": "UPDATE risk_assessments SET score = 99",
    "decisions": "UPDATE decisions SET outcome = 'MANUAL_REVIEW'",
    "documents": "UPDATE documents SET size_bytes = 11",
    "idempotency_keys": "UPDATE idempotency_keys SET scope = 'other'",
}
SEEDED = {
    "checklist_items": "UPDATE checklist_items SET mandatory = 0",
    "checklist_templates": "UPDATE checklist_templates SET created_at = 'x'",
    "classification_rules": "UPDATE classification_rules SET confidence_bp = 1",
    "watchlist_entries": "UPDATE watchlist_entries SET name = 'x'",
}
HASH = "0" * 64


def seed_row(engine: Engine, table: str) -> None:
    with engine.begin() as conn:
        case_id = insert_case(conn)
        conn.execute(text(CASE_SQL[table]), {"c": case_id, "t": NOW, "h": HASH})


def expect_rejected(engine: Engine, sql: str) -> None:
    with engine.connect() as conn:
        with pytest.raises(DatabaseError, match="append-only"):
            conn.execute(text(sql))
        conn.rollback()


@pytest.mark.nfr("NFR-02")
@pytest.mark.parametrize("table", sorted(UPDATES))
def test_nfr02_update_is_rejected_on_append_only_tables(engine: Engine, table: str) -> None:
    """NFR-02 / E1-S4 AC5: UPDATE on an append-only table raises (trigger)."""
    seed_row(engine, table)
    expect_rejected(engine, UPDATES[table])


@pytest.mark.nfr("NFR-02")
@pytest.mark.parametrize("table", sorted(UPDATES))
def test_nfr02_delete_is_rejected_on_append_only_tables(engine: Engine, table: str) -> None:
    """NFR-02 / E1-S4 AC5: DELETE on an append-only table raises (trigger)."""
    seed_row(engine, table)
    expect_rejected(engine, f"DELETE FROM {table}")


@pytest.mark.nfr("NFR-05")
@pytest.mark.parametrize("table", sorted(SEEDED))
def test_nfr05_seeded_tables_reject_update_and_delete(engine: Engine, table: str) -> None:
    """NFR-05: seeded reference tables change only through new migrations."""
    expect_rejected(engine, SEEDED[table])
    expect_rejected(engine, f"DELETE FROM {table}")


@pytest.mark.nfr("NFR-02")
def test_nfr02_rejected_update_leaves_the_row_unchanged(engine: Engine) -> None:
    """NFR-02: after a rejected UPDATE the stored row is intact."""
    seed_row(engine, "audit_log")
    expect_rejected(engine, UPDATES["audit_log"])
    with engine.connect() as conn:
        assert conn.execute(text("SELECT actor FROM audit_log")).scalar_one() == "a"


@pytest.mark.nfr("NFR-02")
@pytest.mark.parametrize("repo", [StateHistoryRepository, AuditRepository])
def test_nfr02_repositories_expose_no_update_or_delete(repo: type[Any]) -> None:
    """E1-S4 AC5: append-only repositories offer only add and read methods."""
    public = {n for n, _ in inspect.getmembers(repo, inspect.isfunction) if not n.startswith("_")}
    assert "add" in public
    assert all(n == "add" or n.startswith(("list_", "get", "find", "count")) for n in public)
    assert not any(w in n for n in public for w in ("update", "delete", "remove", "set", "save"))


@pytest.mark.nfr("NFR-08")
def test_nfr08_locked_case_rejects_any_update(engine: Engine) -> None:
    """NFR-08: an APPROVED or REJECTED case cannot be updated at all (trigger)."""
    for state in ("APPROVED", "REJECTED"):
        with engine.begin() as conn:
            case_id = insert_case(conn, state=state)
        for sql in (
            "UPDATE cases SET state = 'CLASSIFIED' WHERE case_id = :c",
            "UPDATE cases SET updated_at = 'x' WHERE case_id = :c",
        ):
            with engine.connect() as conn:
                with pytest.raises(DatabaseError, match="case is locked"):
                    conn.execute(text(sql), {"c": case_id})
                conn.rollback()


@pytest.mark.nfr("NFR-08")
def test_nfr08_open_case_allows_state_and_updated_at_only(engine: Engine) -> None:
    """Data model: cases change only state and updated_at; other columns are guarded."""
    with engine.begin() as conn:
        case_id = insert_case(conn)
        conn.execute(
            text("UPDATE cases SET state='DOCS_SUBMITTED', updated_at='u' WHERE case_id=:c"),
            {"c": case_id},
        )
    with engine.connect() as conn:
        with pytest.raises(DatabaseError, match="only state and updated_at"):
            conn.execute(text("UPDATE cases SET name='Other' WHERE case_id=:c"), {"c": case_id})
        conn.rollback()
        with pytest.raises(DatabaseError, match="never deleted"):
            conn.execute(text("DELETE FROM cases WHERE case_id=:c"), {"c": case_id})
        conn.rollback()


PROFILE_SQL = (
    "INSERT INTO case_profiles (case_id, date_of_birth, annual_income, occupation_category,"
    " country_code, state_code, updated_at) VALUES (:c, '1990-04-12', 3000000, 'SALARIED', 'IN',"
    " 'MH', 't')"
)


@pytest.mark.ac("AC-01")
def test_ac01_5_profile_editable_only_while_initiated(engine: Engine) -> None:
    """AC-01.5 (defence in depth): trigger blocks profile UPDATE/DELETE once not INITIATED."""
    with engine.begin() as conn:
        case_id = insert_case(conn)
        conn.execute(text(PROFILE_SQL), {"c": case_id})
        conn.execute(
            text("UPDATE case_profiles SET annual_income = 1 WHERE case_id=:c"), {"c": case_id}
        )  # allowed while INITIATED
        conn.execute(text("UPDATE cases SET state='DOCS_SUBMITTED' WHERE case_id=:c"),
                     {"c": case_id})  # fmt: skip
    for sql in (
        "UPDATE case_profiles SET annual_income = 2 WHERE case_id=:c",
        "DELETE FROM case_profiles WHERE case_id=:c",
    ):
        with engine.connect() as conn:
            with pytest.raises(DatabaseError, match="profile is locked"):
                conn.execute(text(sql), {"c": case_id})
            conn.rollback()
