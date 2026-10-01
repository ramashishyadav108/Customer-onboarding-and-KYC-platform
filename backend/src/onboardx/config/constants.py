"""Static configuration values shared across layers."""

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = BACKEND_DIR / "migrations"
MIGRATION_VERSIONS_DIR = MIGRATIONS_DIR / "versions"
MIGRATION_MANIFEST = MIGRATIONS_DIR / "manifest.json"
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"

CORRELATION_HEADER = "X-Correlation-ID"
MAX_CORRELATION_ID_LENGTH = 128
