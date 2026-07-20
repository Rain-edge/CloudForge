"""
请求追踪中间件 — 为每个 HTTP 请求注入唯一 ID 和 Trace 上下文。
===================================================================
本中间件在每次 HTTP 请求的入口做三件事：

  1. Request ID 注入
     从 X-Request-ID 请求头读取，不存在则生成 UUID4。
     响应头中回传 X-Request-ID，客户端和 Nginx/Azure API Management 可用它追踪。

  2. OpenTelemetry Trace 关联
     从当前 Span 提取 trace_id 和 span_id，
     绑定到 structlog 上下文变量，确保日志中包含 Trace 信息。

  3. 结构化日志上下文（structlog contextvars）
     structlog 使用 contextvars 实现线程/协程安全的上下文字典。
     bind_contextvars() 将变量推入栈顶，
     unbind_contextvars() 在请求结束时清理，防止泄漏到下一个请求。

请求处理流程：
  Browser → Nginx Ingress → Uvicorn → RequestIDMiddleware → 路由函数
                                                    ├── 读/生成 request_id
                                                    ├── 注入 trace_id 到日志
                                                    └── 在响应中回传 X-Request-ID
"""
import uuid

import structlog
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Starlette 中间件：注入请求 ID 和 Trace 上下文到日志。

    使用方法：
      app.add_middleware(RequestIDMiddleware)

    中间件执行顺序：
      FastAPI 按 add_middleware() 的逆序执行（后添加的先执行），
      本中间件在 telemetry/tracing 之后添加，确保当前 Span 已创建。
    """

    async def dispatch(self, request: Request, call_next):
        """Starlette 中间件调度入口。

        Args:
            request:   Starlette Request 对象（包含 headers, method, path 等）
            call_next: 调用链中的下一个中间件（或路由处理器）

        Returns:
            Response: 添加了 X-Request-ID 响应头的 HTTP 响应
        """
        # ── Step 1: 获取或生成 Request ID ─────────────────
        # 优先使用上游传入的 X-Request-ID（分布式追踪的入口统一）
        # 如果没有，生成一个 UUID4（128 位随机数）
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # 将 request_id 绑定到 structlog 上下文，后续所有日志自动包含它
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # ── Step 2: 注入 Trace 上下文到日志 ──────────────
        # 从 OpenTelemetry 的当前 Span 提取 trace_id 和 span_id
        # span_context.is_valid → 确认 Span 正在被记录（Otel 插桩已生效）
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            structlog.contextvars.bind_contextvars(
                # 格式化为 32 位/16 位十六进制字符串，与 Jaeger/Tempo UI 保持一致
                trace_id=format(span_context.trace_id, "032x"),
                span_id=format(span_context.span_id, "016x"),
            )

        # ── Step 3: 放行请求，并在响应头中回传 Request ID ─
        try:
            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # ★ try/finally 关键：即使 call_next 抛出异常，也必须清理上下文
            # 否则 trace_id/span_id 会"泄漏"到协程池中的下一个请求
            structlog.contextvars.unbind_contextvars("trace_id", "span_id")
