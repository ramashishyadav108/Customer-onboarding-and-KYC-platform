"""Append-only triggers (NFR-02), published rule-set immutability and locked-case guard.

SQLite variant. A PostgreSQL variant would use the same names with PL/pgSQL functions.
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

APPEND_ONLY = [
    "checklist_templates",
    "checklist_items",
    "documents",
    "document_rejections",
    "classification_rules",
    "classification_results",
    "screening_results",
    "watchlist_entries",
    "watchlist_deactivations",
    "risk_assessments",
    "decisions",
    "overrides",
    "accounts",
    "notifications",
    "state_history",
    "audit_log",
    "idempotency_keys",
]


def _guard(name: str, timing_event: str, table: str, message: str, when: str = "") -> str:
    condition = f"\n  WHEN {when}" if when else ""
    return (
        f"CREATE TRIGGER {name} BEFORE {timing_event} ON {table}{condition}\n"
        f"BEGIN SELECT RAISE(ABORT, '{message}'); END"
    )


def _statements() -> list[str]:
    out: list[str] = []
    for table in APPEND_ONLY:
        msg = f"append-only table: {table}"
        out.append(_guard(f"{table}_no_update", "UPDATE", table, msg))
        out.append(_guard(f"{table}_no_delete", "DELETE", table, msg))
    published = "OLD.status = 'PUBLISHED'"
    msg = "published rule set is immutable"
    out.append(
        _guard("risk_rule_sets_published_no_update", "UPDATE", "risk_rule_sets", msg, published)
    )
    out.append(
        _guard("risk_rule_sets_published_no_delete", "DELETE", "risk_rule_sets", msg, published)
    )
    out.append(
        _guard(
            "risk_rule_sets_no_published_insert",
            "INSERT",
            "risk_rule_sets",
            "rule sets are inserted as DRAFT and then published",
            "NEW.status = 'PUBLISHED'",
        )
    )
    locked = "OLD.state IN ('APPROVED','REJECTED')"
    out.append(_guard("cases_locked_no_update", "UPDATE", "cases", "case is locked", locked))
    out.append(_guard("cases_no_delete", "DELETE", "cases", "cases are never deleted"))
    out.append(
        _guard(
            "cases_immutable_columns",
            "UPDATE",
            "cases",
            "only state and updated_at may change",
            "NEW.case_id <> OLD.case_id OR NEW.name <> OLD.name OR NEW.contact <> OLD.contact"
            " OR NEW.product <> OLD.product OR NEW.checklist_version <> OLD.checklist_version"
            " OR NEW.created_at <> OLD.created_at",
        )
    )
    not_initiated = "(SELECT state FROM cases WHERE case_id = OLD.case_id) <> 'INITIATED'"
    msg = "profile is locked once the case leaves INITIATED"
    out.append(
        _guard("case_profiles_locked_no_update", "UPDATE", "case_profiles", msg, not_initiated)
    )
    out.append(
        _guard("case_profiles_locked_no_delete", "DELETE", "case_profiles", msg, not_initiated)
    )
    return out


def upgrade() -> None:
    for statement in _statements():
        op.execute(statement)


def downgrade() -> None:
    raise NotImplementedError("migrations are append-only and forward-only (NFR-05)")
