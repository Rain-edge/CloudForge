"""OpenTelemetry 分布式追踪 — 自动插桩 FastAPI 与 SQLAlchemy。

通过 OTLP/gRPC 将 Span 导出到 Tempo（K8s）或 Jaeger（本地），
为每个 HTTP 请求与 SQL 查询自动生成 Span，构成可观测性三支柱中的 Tracing。
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
    """初始化 OTel 自动插桩；安全可重复调用。"""
    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    # OTLP 不可达时回退到控制台输出，保证本地开发不阻塞启动
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

    # instrument 已执行过会抛异常，捕获以避免中断应用启动
    try:
        FastAPIInstrumentor().instrument_app(app)
    except Exception:
        logger.warning("OTel: FastAPIInstrumentor already instrumented or failed")

    # enable_commenter：在 SQL 语句注入 trace 注释，便于慢查询日志关联
    try:
        SQLAlchemyInstrumentor().instrument(
            enable_commenter=True, commenter_options={}
        )
    except Exception:
        logger.warning("OTel: SQLAlchemyInstrumentor already instrumented or failed")
