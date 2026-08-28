"""structlog 全局配置 — 统一日志格式。

按 CF_LOG_FORMAT 选择输出格式（K8s 环境由 ConfigMap 注入）：
  - json：JSONRenderer，字段含 request_id / trace_id / span_id，
          Loki 采集后可在 Grafana 点击 trace_id 跳转 Tempo 调用链
  - console：可读的 key-value 格式，本地开发用

必须在应用启动早期调用（main.py import 时执行），
保证后续所有 structlog.get_logger() 输出都走统一格式。
"""
import logging

import structlog
from structlog.dev import ConsoleRenderer

from app.core.config import settings


def setup_logging(log_format: str | None = None) -> None:
    """配置 structlog；可重复调用（幂等），log_format 缺省时读取 CF_LOG_FORMAT。"""
    fmt = (log_format or settings.log_format).lower()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # 公共 processor 链：先合并 contextvars（中间件绑定的 request_id/trace_id/span_id），
    # 再加日志级别和时间戳，最后按格式渲染
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if fmt == "json":
        processors = shared_processors + [structlog.processors.JSONRenderer()]
    else:
        processors = shared_processors + [ConsoleRenderer()]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
