"""Seed checklist v1 for Savings, Current and NRE (specs/document-checklist_spec.md)."""

import json

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

CREATED_AT = "2026-10-01T00:00:00Z"
ID_ALL = ["PAN", "AADHAAR", "PASSPORT"]
ADDRESS = ["AADHAAR", "PASSPORT", "UTILITY_BILL"]
PHOTO = ["PHOTOGRAPH"]

# (product, item_code, mandatory, accepted_classes)
ITEMS = [
    ("Savings", "ID_PROOF", 1, ID_ALL),
    ("Savings", "ADDRESS_PROOF", 1, ADDRESS),
    ("Savings", "PHOTOGRAPH", 1, PHOTO),
    ("Current", "ID_PROOF", 1, ID_ALL),
    ("Current", "ADDRESS_PROOF", 1, ADDRESS),
    ("Current", "PHOTOGRAPH", 1, PHOTO),
    ("Current", "BUSINESS_PROOF", 1, ["GST_CERTIFICATE"]),
    ("NRE", "ID_PROOF", 1, ["PASSPORT"]),
    ("NRE", "ADDRESS_PROOF", 1, ADDRESS),
    ("NRE", "PHOTOGRAPH", 1, PHOTO),
    ("NRE", "OVERSEAS_ADDRESS_PROOF", 1, ["VISA"]),
]


def upgrade() -> None:
    bind = op.get_bind()
    template = sa.text(
        "INSERT INTO checklist_templates (product, version, created_at) VALUES (:p, 1, :t)"
    )
    for product in ("Savings", "Current", "NRE"):
        bind.execute(template, {"p": product, "t": CREATED_AT})
    item = sa.text(
        "INSERT INTO checklist_items (product, version, item_code, mandatory, accepted_classes)"
        " VALUES (:p, 1, :code, :m, :classes)"
    )
    for product, code, mandatory, classes in ITEMS:
        bind.execute(
            item, {"p": product, "code": code, "m": mandatory, "classes": json.dumps(classes)}
        )


def downgrade() -> None:
    raise NotImplementedError("migrations are append-only and forward-only (NFR-05)")
