"""Composition root: builds the FastAPI app from settings (exempt from layering)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import Engine

from onboardx.config.logging_setup import configure_logging
from onboardx.config.settings import Settings, load_settings
from onboardx.controllers.middleware import CorrelationMiddleware
from onboardx.controllers.routers import health
from onboardx.repositories.database import create_db_engine, create_session_factory


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    """Create the app; with no settings they are loaded from the environment (fails fast)."""
    resolved = settings or load_settings()
    configure_logging(resolved.log_level)
    owns_engine = engine is None
    db_engine = engine or create_db_engine(resolved.database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        if owns_engine:
            db_engine.dispose()

    app = FastAPI(title="OnboardX", lifespan=lifespan)
    app.state.settings = resolved
    app.state.engine = db_engine
    app.state.session_factory = create_session_factory(db_engine)
    app.add_middleware(CorrelationMiddleware)
    app.include_router(health.router)
    return app
