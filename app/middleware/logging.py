"""请求追踪中间件 — 为每个 HTTP 请求注入 Request-ID 与 Trace 上下文。

将 request_id 与当前 Span 的 trace_id/span_id 绑定到 structlog contextvars，
使结构化日志与 Tempo/Jaeger 中的 Trace 可互相关联。
"""
import uuid

import structlog
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """注入 Request-ID 与 Trace 上下文到日志。

    需在 setup_telemetry 之后注册，确保当前 Span 已创建。"""

    async def dispatch(self, request: Request, call_next):
        """读/生成 request_id → 绑定日志上下文 → 回传响应头。"""
        # 优先复用上游 X-Request-ID，便于跨服务串联
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # 绑定当前 Span 的 trace_id/span_id，日志即可跳转到 Tempo
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            structlog.contextvars.bind_contextvars(
                trace_id=format(span_context.trace_id, "032x"),
                span_id=format(span_context.span_id, "016x"),
            )

        try:
            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # 必须清理 contextvars，否则 trace_id 会泄漏到协程池中的下一个请求
            structlog.contextvars.unbind_contextvars("trace_id", "span_id")
