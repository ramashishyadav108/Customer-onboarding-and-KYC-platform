"""Manual review policy reason and pending staff sign-ups (AC-14, AC-15).

* `decisions.reason_code` gains MANUAL_POLICY (every case goes to a compliance officer when the
  deployment runs REVIEW_POLICY=manual). SQLite cannot alter a CHECK constraint, so the table is
  rebuilt with the same columns; rows are copied verbatim and the append-only triggers recreated.
* `users.pending` marks a staff account that was requested at sign-up and awaits admin approval.
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

REASONS = (
    "'AML_HIT','PEP_HIT','DOC_UNRECOGNISED','RISK_MEDIUM','RISK_HIGH','AUTO_APPROVED',"
    "'MANUAL_POLICY'"
)

STATEMENTS = [
    f"""CREATE TABLE decisions_new (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, decision_id TEXT NOT NULL UNIQUE,
  case_id TEXT NOT NULL UNIQUE REFERENCES cases (case_id) ON DELETE RESTRICT,
  type TEXT NOT NULL CHECK (type = 'AUTO'),
  outcome TEXT NOT NULL CHECK (outcome IN ('APPROVED','MANUAL_REVIEW')),
  reason_code TEXT NOT NULL CHECK (reason_code IN ({REASONS})),
  rule_version INTEGER NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL)""",
    "INSERT INTO decisions_new SELECT * FROM decisions",
    "DROP TABLE decisions",
    "ALTER TABLE decisions_new RENAME TO decisions",
    "ALTER TABLE users ADD COLUMN pending INTEGER NOT NULL DEFAULT 0 CHECK (pending IN (0, 1))",
]


def _guard(table: str, timing_event: str) -> str:
    name = f"{table}_no_{timing_event.lower()}"
    return (
        f"CREATE TRIGGER {name} BEFORE {timing_event} ON {table}\n"
        f"BEGIN SELECT RAISE(ABORT, 'append-only table: {table}'); END"
    )


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)
    op.execute(_guard("decisions", "UPDATE"))
    op.execute(_guard("decisions", "DELETE"))
