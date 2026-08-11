from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from farebeacon.api.errors import install_error_handlers
from farebeacon.api.middleware import RequestContextMiddleware
from farebeacon.api.routes import monitors, results, runs, sources, system
from farebeacon.application.common import sync_source_definitions
from farebeacon.config import Settings, get_settings
from farebeacon.infrastructure.db.session import Database, database
from farebeacon.sources.registry import get_source_registry


def create_app(
    *,
    settings: Settings | None = None,
    app_database: Database | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_database = app_database or database
    resolved_settings.require_api_token()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        with resolved_database.session() as session:
            sync_source_definitions(session, get_source_registry())
            session.commit()
        yield

    application = FastAPI(
        title="FareBeacon API",
        summary="Agent-friendly open-source airfare monitoring hub",
        description=(
            "FareBeacon normalizes results from independent flight-search sources, preserves price "
            "history, and exposes asynchronous high-level operations through one HTTP API."
        ),
        version=resolved_settings.version,
        lifespan=lifespan,
        contact={"name": "FareBeacon maintainers"},
        license_info={
            "name": "Apache-2.0",
            "identifier": "Apache-2.0",
        },
        openapi_tags=[
            {
                "name": "system",
                "description": "Liveness, readiness, and build identity.",
            },
            {
                "name": "monitors",
                "description": "Persistent airfare search intentions.",
            },
            {"name": "runs", "description": "Asynchronous monitor executions."},
            {
                "name": "results",
                "description": "Normalized offers and observation history.",
            },
            {"name": "sources", "description": "Installed acquisition adapters."},
        ],
    )
    application.state.settings = resolved_settings
    application.state.database = resolved_database
    application.add_middleware(RequestContextMiddleware)
    install_error_handlers(application)
    application.include_router(system.router)
    application.include_router(monitors.router)
    application.include_router(runs.router)
    application.include_router(results.router)
    application.include_router(sources.router)
    return application


logging.basicConfig(level=get_settings().log_level, format="%(levelname)s %(name)s %(message)s")
app = create_app()
