"""Start the backend: migration guard, alembic upgrade head, then uvicorn (default :8000)."""

import os

import uvicorn

from onboardx.config.constants import MIGRATION_MANIFEST, MIGRATION_VERSIONS_DIR
from onboardx.config.migration_guard import assert_migrations_unmodified
from onboardx.config.settings import load_settings
from onboardx.main import create_app
from onboardx.repositories.database import create_db_engine, upgrade_to_head


def main() -> None:
    settings = load_settings()
    assert_migrations_unmodified(MIGRATION_VERSIONS_DIR, MIGRATION_MANIFEST)
    engine = create_db_engine(settings.database_url)
    upgrade_to_head(engine)
    app = create_app(settings, engine)
    uvicorn.run(
        app,
        host=os.environ.get("BACKEND_HOST", "127.0.0.1"),
        port=int(os.environ.get("BACKEND_PORT", "8000")),
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
