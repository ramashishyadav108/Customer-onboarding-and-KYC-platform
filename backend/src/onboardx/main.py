"""Composition root: builds the FastAPI app from settings (exempt from layering)."""

import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import Engine

from onboardx.config.clock import SystemClock
from onboardx.config.logging_setup import configure_logging
from onboardx.config.settings import Settings, load_settings
from onboardx.controllers.dependencies.services import build_services
from onboardx.controllers.error_handlers import register_error_handlers
from onboardx.controllers.middleware import CorrelationMiddleware
from onboardx.controllers.routers import (
    admin_reports,
    admin_rule_sets,
    admin_watchlist,
    auth,
    cases,
    documents,
    health,
    leads,
    pipeline,
    products,
    review,
)
from onboardx.domain.ports import Clock, NotificationSender
from onboardx.repositories.database import create_db_engine, create_session_factory
from onboardx.repositories.unit_of_work import make_uow_factory

ROUTERS = (
    health,
    auth,
    leads,
    cases,
    documents,
    pipeline,
    products,
    review,
    admin_rule_sets,
    admin_watchlist,
    admin_reports,
)


def create_app(
    settings: Settings | None = None,
    engine: Engine | None = None,
    clock: Clock | None = None,
    notification_sender: NotificationSender | None = None,
) -> FastAPI:
    """Create the app; with no settings they are loaded from the environment (fails fast)."""
    resolved = settings or load_settings()
    configure_logging(resolved.log_level)
    owns_engine = engine is None
    db_engine = engine or create_db_engine(resolved.database_url)
    session_factory = create_session_factory(db_engine)
    secret = resolved.jwt_secret
    if secret is None:
        secret = secrets.token_urlsafe(32)
        logging.getLogger("onboardx.startup").warning(
            "JWT_SECRET not set: using an ephemeral secret, tokens die on restart"
        )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        if owns_engine:
            db_engine.dispose()

    app = FastAPI(title="OnboardX", lifespan=lifespan)
    app.state.settings = resolved
    app.state.engine = db_engine
    app.state.session_factory = session_factory
    app.state.services = build_services(
        resolved,
        make_uow_factory(session_factory),
        clock or SystemClock(),
        secret,
        notification_sender,
    )
    register_error_handlers(app)
    app.add_middleware(CorrelationMiddleware)
    for module in ROUTERS:
        app.include_router(module.router)
    return app
