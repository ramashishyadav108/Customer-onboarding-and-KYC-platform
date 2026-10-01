"""Hand-computable history fixture for the report tests (AC-10). Synthetic data only.

Rows are inserted with raw SQL (INSERT is allowed on append-only tables) so every timestamp is
exact. T0 is 2026-09-01T00:00:00Z; offsets are whole seconds.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Connection, Engine, text

from helpers import FakeClock, ensure_template

T0 = datetime(2026, 9, 1, tzinfo=UTC)
DAY = 86400

AUTO = ("APPROVED", "AUTO_APPROVED")
# name -> (product, [(state, offset)], decision (outcome, reason) | None, override (kind, reason))
Path = list[tuple[str, int]]
CASES: dict[str, tuple[str, Path, tuple[str, str] | None, tuple[str, str] | None]] = {
    "S1": ("Savings", [("INITIATED", 0), ("DOCS_SUBMITTED", 100), ("SCREENED", 160),
                       ("CLASSIFIED", 220), ("APPROVED", 280)], AUTO, None),
    "S2": ("Savings", [("INITIATED", 0), ("DOCS_SUBMITTED", 200), ("SCREENED", 260),
                       ("CLASSIFIED", 320), ("APPROVED", 380)], AUTO, None),
    "S3": ("Savings", [("INITIATED", 0), ("DOCS_SUBMITTED", 50), ("SCREENED", 100),
                       ("CLASSIFIED", 150), ("MANUAL_REVIEW", 150), ("REJECTED", 1000)],
           ("MANUAL_REVIEW", "AML_HIT"), ("REJECT", "CONFIRMED_WATCHLIST_MATCH")),
    "S4": ("Savings", [("INITIATED", 0), ("DOCS_SUBMITTED", 10)], None, None),
    "S5": ("Savings", [("INITIATED", 4 * DAY), ("DOCS_SUBMITTED", 4 * DAY + 120),
                       ("SCREENED", 4 * DAY + 180), ("CLASSIFIED", 4 * DAY + 240),
                       ("APPROVED", 4 * DAY + 300)], AUTO, None),
    "C1": ("Current", [("INITIATED", 0), ("DOCS_SUBMITTED", 100), ("SCREENED", 200),
                       ("CLASSIFIED", 300), ("MANUAL_REVIEW", 300)],
           ("MANUAL_REVIEW", "RISK_MEDIUM"), None),
    "C2": ("Current", [("INITIATED", 0), ("DOCS_SUBMITTED", 100), ("SCREENED", 200),
                       ("CLASSIFIED", 300), ("MANUAL_REVIEW", 300), ("APPROVED", 900)],
           ("MANUAL_REVIEW", "RISK_MEDIUM"), ("APPROVE", "RISK_ACCEPTED")),
    "C3": ("Current", [("INITIATED", 0), ("DOCS_SUBMITTED", 60), ("SCREENED", 120),
                       ("CLASSIFIED", 180), ("MANUAL_REVIEW", 180), ("REJECTED", 600)],
           ("MANUAL_REVIEW", "DOC_UNRECOGNISED"), ("REJECT", "RISK_TOO_HIGH")),
    "N1": ("NRE", [("INITIATED", 0), ("DOCS_SUBMITTED", 30), ("SCREENED", 60),
                   ("CLASSIFIED", 90), ("MANUAL_REVIEW", 90), ("REJECTED", 390)],
           ("MANUAL_REVIEW", "RISK_HIGH"), ("REJECT", "RISK_TOO_HIGH")),
    "N2": ("NRE", [("INITIATED", 0)], None, None),
}  # fmt: skip


def iso(offset: int) -> str:
    return (T0 + timedelta(seconds=offset)).strftime("%Y-%m-%dT%H:%M:%SZ")


def set_clock(clock: FakeClock, moment: datetime) -> None:
    clock.advance(int((moment - clock.now()).total_seconds()))


def insert_history_case(
    conn: Connection,
    product: str,
    path: Path,
    decision: tuple[str, str] | None = None,
    override: tuple[str, str] | None = None,
) -> str:
    """Insert one case with its full history, optional decision and override; return case_id."""
    ensure_template(conn, product, 1)
    case_id = str(uuid.uuid4())
    state, last = path[-1]
    conn.execute(
        text(
            "INSERT INTO cases (case_id, name, contact, product, state, checklist_version,"
            " created_at, updated_at) VALUES (:c, 'Test Person One', '9999999921', :p, :s, 1,"
            " :a, :b)"
        ),
        {"c": case_id, "p": product, "s": state, "a": iso(path[0][1]), "b": iso(last)},
    )
    previous: str | None = None
    for to_state, offset in path:
        conn.execute(
            text(
                "INSERT INTO state_history (history_id, case_id, from_state, to_state, actor,"
                " reason_code, idempotency_key, created_at) VALUES (:h, :c, :f, :t, 'seed', NULL,"
                " NULL, :at)"
            ),
            {"h": str(uuid.uuid4()), "c": case_id, "f": previous, "t": to_state, "at": iso(offset)},
        )
        previous = to_state
    if decision is not None:
        insert_decision(conn, case_id, decision, decision_offset(path))
    if override is not None:
        insert_override(conn, case_id, override, last)
    return case_id


def decision_offset(path: Path) -> int:
    """The decision step runs when the case is CLASSIFIED."""
    return next(offset for state, offset in path if state == "CLASSIFIED")


def insert_decision(conn: Connection, case_id: str, decision: tuple[str, str], offset: int) -> None:
    conn.execute(
        text(
            "INSERT INTO decisions (decision_id, case_id, type, outcome, reason_code,"
            " rule_version, actor, created_at) VALUES (:d, :c, 'AUTO', :o, :r, 1, 'seed', :at)"
        ),
        {
            "d": str(uuid.uuid4()),
            "c": case_id,
            "o": decision[0],
            "r": decision[1],
            "at": iso(offset),
        },
    )


def insert_override(conn: Connection, case_id: str, override: tuple[str, str], offset: int) -> None:
    conn.execute(
        text(
            "INSERT INTO overrides (override_id, case_id, actor, previous_state, decision,"
            " reason_code, comment, rule_version, created_at) VALUES (:o, :c, 'officer1',"
            " 'MANUAL_REVIEW', :d, :r, NULL, 1, :at)"
        ),
        {
            "o": str(uuid.uuid4()),
            "c": case_id,
            "d": override[0],
            "r": override[1],
            "at": iso(offset),
        },
    )


def seed_fixture(engine: Engine) -> dict[str, str]:
    """Insert every case of CASES; returns name -> case_id."""
    ids: dict[str, str] = {}
    with engine.begin() as conn:
        for name, (product, path, decision, override) in CASES.items():
            ids[name] = insert_history_case(conn, product, path, decision, override)
    return ids
