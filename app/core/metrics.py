"""
Prometheus metrics via prometheus-fastapi-instrumentator.
Exposes /metrics for Prometheus scraping.
"""
from prometheus_client import CollectorRegistry
from prometheus_fastapi_instrumentator import Instrumentator


def setup_metrics(app):
    registry = CollectorRegistry(auto_describe=True)
    instrumentator = Instrumentator(
        registry=registry,
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_instrument_requests_inprogress=True,
        should_round_latency_decimals=True,
    )
    instrumentator.instrument(app).expose(app, endpoint="/metrics")
