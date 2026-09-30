"""Seed 10 synthetic watchlist entries: 5 AML and 5 PEP (specs/screening_spec.md).

All names are fictitious. name_tokens is the normalised, sorted token string (NFKC, lowercase,
punctuation stripped) used by the matcher; alias_tokens holds the same for each alias.
"""

import json
import re
import unicodedata

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

CREATED_AT = "2026-10-01T00:00:00Z"

# (entry_id, name, aliases, list_type)
ENTRIES = [
    ("10000000-0000-4000-8000-000000000001", "Test Person One", ["T P One"], "AML"),
    ("10000000-0000-4000-8000-000000000002", "Sample Launderer Alpha", [], "AML"),
    ("10000000-0000-4000-8000-000000000003", "Synthetic Smuggler Beta", ["Beta Smuggler"], "AML"),
    ("10000000-0000-4000-8000-000000000004", "Fictional Fraudster Gamma", [], "AML"),
    ("10000000-0000-4000-8000-000000000005", "Demo Racketeer Delta", ["D Racketeer"], "AML"),
    ("10000000-0000-4000-8000-000000000006", "Mock Minister Epsilon", [], "PEP"),
    ("10000000-0000-4000-8000-000000000007", "Example Senator Zeta", ["Senator Zeta"], "PEP"),
    ("10000000-0000-4000-8000-000000000008", "Placeholder Governor Eta", [], "PEP"),
    ("10000000-0000-4000-8000-000000000009", "Imaginary Ambassador Theta", [], "PEP"),
    ("10000000-0000-4000-8000-000000000010", "Notional Mayor Iota", ["Mayor Iota"], "PEP"),
]


def _tokens(name: str) -> str:
    text = unicodedata.normalize("NFKC", name).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(sorted(text.split()))


def upgrade() -> None:
    insert = sa.text(
        "INSERT INTO watchlist_entries (entry_id, name, aliases, list_type, name_tokens,"
        " alias_tokens, added_by, created_at) VALUES (:id, :name, :aliases, :list_type,"
        " :tokens, :alias_tokens, 'system', :t)"
    )
    bind = op.get_bind()
    for entry_id, name, aliases, list_type in ENTRIES:
        bind.execute(
            insert,
            {
                "id": entry_id,
                "name": name,
                "aliases": json.dumps(aliases),
                "list_type": list_type,
                "tokens": _tokens(name),
                "alias_tokens": json.dumps([_tokens(a) for a in aliases]),
                "t": CREATED_AT,
            },
        )


def downgrade() -> None:
    raise NotImplementedError("migrations are append-only and forward-only (NFR-05)")
