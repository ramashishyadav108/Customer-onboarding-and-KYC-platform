"""Seed filename-prefix classifier rules v1 (specs/document-classification-stub_spec.md)."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

# (prefix, doc_class, confidence_bp); all VERIFIED. Priority follows the listed order.
RULES = [
    ("pan_", "PAN", 9500),
    ("aadhaar_", "AADHAAR", 9500),
    ("passport_", "PASSPORT", 9500),
    ("utility-bill_", "UTILITY_BILL", 9500),
    ("photograph_", "PHOTOGRAPH", 9500),
    ("gst-certificate_", "GST_CERTIFICATE", 9500),
    ("visa_", "VISA", 9500),
]


def upgrade() -> None:
    insert = sa.text(
        "INSERT INTO classification_rules"
        " (rule_version, prefix, doc_class, status, confidence_bp, priority)"
        " VALUES (1, :prefix, :doc_class, 'VERIFIED', :bp, :priority)"
    )
    bind = op.get_bind()
    for priority, (prefix, doc_class, bp) in enumerate(RULES, start=1):
        bind.execute(
            insert, {"prefix": prefix, "doc_class": doc_class, "bp": bp, "priority": priority}
        )


def downgrade() -> None:
    raise NotImplementedError("migrations are append-only and forward-only (NFR-05)")
