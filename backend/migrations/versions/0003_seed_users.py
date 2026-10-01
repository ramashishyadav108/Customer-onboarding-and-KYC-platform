"""Seed four synthetic users, one per role (E1-S2 AC2).

Passwords are obviously synthetic demo values, documented here only (README-level comment):

    prospect1 -> demo-prospect1-pass      (role prospect)
    analyst1  -> demo-analyst1-pass       (role kyc-analyst)
    officer1  -> demo-officer1-pass       (role compliance-officer)
    admin1    -> demo-admin1-pass         (role admin)

Only salted PBKDF2-HMAC-SHA256 hashes are stored (format ``pbkdf2_sha256$iterations$salt$hash``,
per-user salt). They were precomputed so this migration does no key stretching at startup.
Never use these values outside local verification mode.
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

CREATED_AT = "2026-10-01T00:00:00Z"
USERS = [
    (
        "00000000-0000-4000-8000-000000000001",
        "prospect1",
        "prospect",
        "pbkdf2_sha256$210000$449e2807c4d9f12935f8956d4f522ee6$"
        "427cb88e075c11427f194f90cea41360f81ce9b265d984c109df510987a16db6",
    ),
    (
        "00000000-0000-4000-8000-000000000002",
        "analyst1",
        "kyc-analyst",
        "pbkdf2_sha256$210000$f8e3d0d46e2fbcc7dbeed7ea0c8a0443$"
        "4ecb703c6387bff5c87fb6b6c56470c86ea3274d8d72f686670db8552a41782a",
    ),
    (
        "00000000-0000-4000-8000-000000000003",
        "officer1",
        "compliance-officer",
        "pbkdf2_sha256$210000$653513fa16b44eeb1a7bdcbf04503180$"
        "75f28acf0020031a523e0b484b91a2e6c06474097955425f3b4cf4bb7c843b8d",
    ),
    (
        "00000000-0000-4000-8000-000000000004",
        "admin1",
        "admin",
        "pbkdf2_sha256$210000$56b899cbb97b7b0c020164e1c6c79b0d$"
        "ec75f94e1bee92c2138bc47322893862758159906c6a5867994b8599f124b32a",
    ),
]


def upgrade() -> None:
    insert = sa.text(
        "INSERT INTO users (user_id, username, password_hash, role, case_id, created_at)"
        " VALUES (:user_id, :username, :password_hash, :role, NULL, :created_at)"
    )
    bind = op.get_bind()
    for user_id, username, role, password_hash in USERS:
        bind.execute(
            insert,
            {
                "user_id": user_id,
                "username": username,
                "password_hash": password_hash,
                "role": role,
                "created_at": CREATED_AT,
            },
        )


def downgrade() -> None:
    raise NotImplementedError("migrations are append-only and forward-only (NFR-05)")
