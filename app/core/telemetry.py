"""
OpenTelemetry setup: auto-instruments FastAPI + SQLAlchemy,
exports traces via OTLP to Tempo/Jaeger (configurable via env var).
"""
import logging
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

logger = logging.getLogger(__name__)


def setup_telemetry(app, service_name: str = "cloudforge"):
    """Set up OTel auto-instrumentation. Safe to call multiple times.

    OTLP endpoint is read from OTEL_EXPORTER_OTLP_ENDPOINT env var,
    defaulting to http://tempo:4317 (K8s).  Set it to
    http://localhost:4317 for local Jaeger.
    """
    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    otlp_endpoint = os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4317"
    )
    try:
        otlp_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint, insecure=True, timeout=3
        )
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        logger.info("OTel: exporting traces to %s", otlp_endpoint)
    except Exception:
        logger.info("OTel: OTLP unavailable, using console exporter")
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)

    try:
        FastAPIInstrumentor().instrument_app(app)
    except Exception:
        logger.warning("OTel: FastAPIInstrumentor already instrumented or failed")

    try:
        SQLAlchemyInstrumentor().instrument(enable_commenter=True, commenter_options={})
    except Exception:
        logger.warning("OTel: SQLAlchemyInstrumentor already instrumented or failed")
