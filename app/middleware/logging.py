import uuid

import structlog
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Inject OpenTelemetry trace_id for log correlation (Loki + Tempo)
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
            structlog.contextvars.unbind_contextvars("trace_id", "span_id")
