"""
OpenTelemetry 分布式链路追踪 — 自动插桩 FastAPI + SQLAlchemy。
=================================================================
本文件负责：
  1. 创建 TracerProvider（绑定服务名 cloudforge）
  2. 将 Trace 数据通过 OTLP/gRPC 协议导出到 Tempo（K8s）或 Jaeger（本地）
  3. 自动为所有 HTTP 请求和数据库查询生成 Span

工作原理：
  - FastAPIInstrumentor：自动为每个路由创建 Span（请求→响应延迟、状态码）
  - SQLAlchemyInstrumentor：自动为每个 SQL 查询创建 Span（SQL 文本、耗时）
  - BatchSpanProcessor：批量发送 Span，不阻塞主线程

环境变量配置：
  OTEL_EXPORTER_OTLP_ENDPOINT  — 导出的 OTLP 收集器地址
    默认值: http://tempo:4317  （K8s 集群内 Tempo 实例）
    本地开发可设为: http://localhost:4317 （Jaeger All-in-One）

可观测性三支柱对应关系：
  Logging  → structlog（app/middleware/logging.py）
  Metrics  → Prometheus（app/core/metrics.py）
  Tracing  → OpenTelemetry（本文件）
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
    """初始化 OpenTelemetry 自动插桩，安全重复调用。

    调用时机：app/main.py 中 app = FastAPI(...) 之后、注册路由之前。

    Args:
        app: FastAPI 应用实例
        service_name: 在 Trace 中标识的服务名（默认 cloudforge）
    """
    # ── Step 1: 创建 TracerProvider，绑定服务名 ──────────
    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    # ── Step 2: 配置 Span 导出器 ──────────────────────────
    # OTLP Exporter：通过 gRPC 将 Span 发送到 Tempo/Jaeger
    # 如果后端不可达，回退到 ConsoleExporter（打印到 stdout）
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

    # 设置全局 TracerProvider（后续所有 Span 都由它管理）
    trace.set_tracer_provider(provider)

    # ── Step 3: 自动插桩 FastAPI 和 SQLAlchemy ──────────
    # instrument_app 为每个 HTTP 请求自动创建/结束 Span
    try:
        FastAPIInstrumentor().instrument_app(app)
    except Exception:
        # 重复调用或插桩失败时记录警告但不中断应用启动
        logger.warning("OTel: FastAPIInstrumentor already instrumented or failed")

    # enable_commenter 自动为 SQL 语句添加注释（便于在数据库慢查询日志中关联 Trace）
    try:
        SQLAlchemyInstrumentor().instrument(
            enable_commenter=True, commenter_options={}
        )
    except Exception:
        logger.warning("OTel: SQLAlchemyInstrumentor already instrumented or failed")
