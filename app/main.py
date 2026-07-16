import os

import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.config import settings
from app.core.database import async_session, engine
from app.core.metrics import refresh_task_metrics, setup_metrics
from app.core.telemetry import setup_telemetry
from app.middleware.logging import RequestIDMiddleware
from app.models.task import Base  # noqa: F401  registers model metadata
from app.routers import health, tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Initial metrics refresh
    await refresh_task_metrics(async_session)
    yield


def create_app() -> FastAPI:
    # Choose renderer: JSON for production/K8s (Loki), console for local dev
    log_format = os.environ.get("CF_LOG_FORMAT", settings.log_format)
    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

    app = FastAPI(title="CloudForge", version="0.1.0", lifespan=lifespan)

    # --- Observability ---
    setup_telemetry(app)
    setup_metrics(app)

    app.add_middleware(RequestIDMiddleware)

    app.include_router(health.router)
    app.include_router(tasks.router)

    return app


app = create_app()
