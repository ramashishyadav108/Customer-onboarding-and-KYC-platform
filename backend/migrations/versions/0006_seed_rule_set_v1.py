"""Seed published risk rule set v1 (specs/classification_spec.md, AC-06.6).

Inserted as DRAFT then published (an INSERT with status PUBLISHED is rejected by trigger).
All numbers are integers (NFR-01). border_states is the synthetic DD-14 list.
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

CREATED_AT = "2026-10-01T00:00:00Z"

WEIGHTS = {"age": 20, "income_band": 25, "occupation_category": 30, "geography": 25}
POINTS = {
    "age": [
        {"label": "under 18", "min_years": 0, "max_years": 17, "points": 100},
        {"label": "18-24", "min_years": 18, "max_years": 24, "points": 30},
        {"label": "25-60", "min_years": 25, "max_years": 60, "points": 0},
        {"label": "61+", "min_years": 61, "max_years": None, "points": 40},
    ],
    "income_band": [
        {"code": "B1", "min_inr": 0, "max_inr": 499999, "points": 10},
        {"code": "B2", "min_inr": 500000, "max_inr": 2499999, "points": 0},
        {"code": "B3", "min_inr": 2500000, "max_inr": 9999999, "points": 30},
        {"code": "B4", "min_inr": 10000000, "max_inr": None, "points": 60},
    ],
    "occupation_category": {
        "SALARIED": 0,
        "RETIRED": 10,
        "STUDENT": 10,
        "SELF_EMPLOYED": 30,
        "BUSINESS_OWNER": 50,
        "CASH_INTENSIVE": 80,
    },
    "geography": {
        "DOMESTIC": 0,
        "FOREIGN_STANDARD": 30,
        "DOMESTIC_BORDER": 40,
        "FOREIGN_HIGH_RISK": 100,
    },
}
GEOGRAPHY_MAP = {
    "IN": "DOMESTIC",
    "GB": "FOREIGN_STANDARD",
    "US": "FOREIGN_STANDARD",
    "AE": "FOREIGN_STANDARD",
    "KP": "FOREIGN_HIGH_RISK",
    "IR": "FOREIGN_HIGH_RISK",
}
BORDER_STATES = ["JK", "PB", "AS"]


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO risk_rule_sets (version, status, weights, points, geography_map,"
            " geography_default, border_states, low_max, medium_max, author, created_at,"
            " published_at) VALUES (1, 'DRAFT', :w, :p, :g, 'FOREIGN_STANDARD', :b, 29, 59,"
            " 'system', :t, NULL)"
        ),
        {
            "w": json.dumps(WEIGHTS),
            "p": json.dumps(POINTS),
            "g": json.dumps(GEOGRAPHY_MAP),
            "b": json.dumps(BORDER_STATES),
            "t": CREATED_AT,
        },
    )
    bind.execute(
        sa.text(
            "UPDATE risk_rule_sets SET status = 'PUBLISHED', published_at = :t WHERE version = 1"
        ),
        {"t": CREATED_AT},
    )


def downgrade() -> None:
    raise NotImplementedError("migrations are append-only and forward-only (NFR-05)")
