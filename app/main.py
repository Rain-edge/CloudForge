import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.database import engine
from app.core.metrics import setup_metrics
from app.core.telemetry import setup_telemetry
from app.middleware.logging import RequestIDMiddleware
from app.models.task import Base  # noqa: F401  registers model metadata
from app.routers import health, tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


def create_app() -> FastAPI:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
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
