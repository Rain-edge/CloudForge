"""
Prometheus metrics via prometheus-fastapi-instrumentator + custom business metrics.
Exposes /metrics for Prometheus scraping.
"""
from prometheus_client import (
    CollectorRegistry,
    Gauge,
    Info,
    PLATFORM_COLLECTOR,
    PROCESS_COLLECTOR,
    GC_COLLECTOR,
)
from prometheus_fastapi_instrumentator import Instrumentator

from app.models.task import TaskStatus


# Custom business metrics (registered on the same registry)
task_count_by_status = Gauge(
    "cloudforge_tasks_total",
    "Total number of tasks by status",
    ["status"],
)

db_pool_size = Gauge(
    "cloudforge_db_pool_size",
    "SQLAlchemy connection pool size",
)

db_pool_checked_out = Gauge(
    "cloudforge_db_pool_checked_out",
    "SQLAlchemy connections currently checked out",
)

db_pool_overflow = Gauge(
    "cloudforge_db_pool_overflow",
    "SQLAlchemy connection pool overflow count",
)

# Application info
app_info = Info("cloudforge_app", "CloudForge application info")

# Pre-initialize status labels so they always appear in /metrics
for _status in TaskStatus:
    task_count_by_status.labels(status=_status.value).set(0)


def setup_metrics(app):
    registry = CollectorRegistry(auto_describe=True)

    # Register default collectors for additional metrics (process, platform, GC)
    registry.register(PROCESS_COLLECTOR)
    registry.register(PLATFORM_COLLECTOR)
    registry.register(GC_COLLECTOR)

    # Register custom gauges on the same registry
    registry.register(task_count_by_status)
    registry.register(db_pool_size)
    registry.register(db_pool_checked_out)
    registry.register(db_pool_overflow)
    registry.register(app_info)

    # Set app info
    app_info.info({"version": "0.1.0", "name": "cloudforge"})

    instrumentator = Instrumentator(
        registry=registry,
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_instrument_requests_inprogress=True,
        should_round_latency_decimals=True,
    )
    instrumentator.instrument(app).expose(app, endpoint="/metrics")


async def refresh_task_metrics(db_session_factory):
    """Refresh task count gauges from the database. Call from a background task or /metrics pre-hook."""
    from sqlalchemy import func, select

    from app.models.task import Task

    try:
        async with db_session_factory() as session:
            result = await session.execute(
                select(Task.status, func.count(Task.id)).group_by(Task.status)
            )
            counts = dict(result.all())

            for status in TaskStatus:
                task_count_by_status.labels(status=status.value).set(
                    counts.get(status, 0)
                )
    except Exception:
        # DB may not be available; gauges remain at zero (pre-initialized)
        pass
