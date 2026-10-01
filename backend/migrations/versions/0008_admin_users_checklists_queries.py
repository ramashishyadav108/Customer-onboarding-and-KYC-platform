"""User activation flag and append-only analyst query tables (AC-11, AC-13).

`users.active` lets an admin deactivate a staff account without deleting it. Queries, responses and
closures are append-only (NFR-02); a query's status is derived (OPEN, ANSWERED, CLOSED). Checklist
versions need no schema change: new versions are INSERTs into the already append-only
`checklist_templates` and `checklist_items` tables (AC-12).
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

APPEND_ONLY = ["case_queries", "query_responses", "query_closures"]

STATEMENTS = [
    "ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))",
    """CREATE TABLE case_queries (
  query_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases (case_id) ON DELETE RESTRICT,
  raised_by TEXT NOT NULL,
  message TEXT NOT NULL CHECK (length(message) BETWEEN 1 AND 500),
  created_at TEXT NOT NULL)""",
    """CREATE TABLE query_responses (
  response_id TEXT PRIMARY KEY,
  query_id TEXT NOT NULL REFERENCES case_queries (query_id) ON DELETE RESTRICT,
  case_id TEXT NOT NULL REFERENCES cases (case_id) ON DELETE RESTRICT,
  author TEXT NOT NULL,
  message TEXT NOT NULL CHECK (length(message) BETWEEN 1 AND 500),
  created_at TEXT NOT NULL)""",
    """CREATE TABLE query_closures (
  query_id TEXT PRIMARY KEY REFERENCES case_queries (query_id) ON DELETE RESTRICT,
  closed_by TEXT NOT NULL,
  created_at TEXT NOT NULL)""",
    "CREATE INDEX ix_queries_case ON case_queries (case_id, created_at)",
    "CREATE INDEX ix_responses_query ON query_responses (query_id, created_at)",
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
    for table in APPEND_ONLY:
        op.execute(_guard(table, "UPDATE"))
        op.execute(_guard(table, "DELETE"))
