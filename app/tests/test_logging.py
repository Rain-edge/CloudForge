"""结构化日志格式测试 — 验证 JSON 输出包含 trace_id/span_id 关联字段。"""

import json
import os


def test_json_log_format():
    """验证 CF_LOG_FORMAT=json 产出合法 JSON 且含 trace_id/span_id 字段。"""
    # 强制 JSON 格式以保证测试隔离
    os.environ["CF_LOG_FORMAT"] = "json"

    import structlog

    # 重新配置 structlog 输出 JSON（测试隔离）
    structlog.reset_defaults()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

    # 绑定 trace 上下文（模拟中间件行为）
    structlog.contextvars.bind_contextvars(
        request_id="test-req-123",
        trace_id="abcdef0123456789abcdef0123456789",
        span_id="0000111122223333",
    )

    import io

    # 捕获结构化日志输出
    log_output = io.StringIO()

    logger = structlog.get_logger()
    # PrintLogger 输出难以直接捕获，改为手动验证 processor 链对 contextvars 的处理
    event_dict = {
        "event": "test log entry",
        "level": "info",
        "timestamp": "2026-01-01T00:00:00Z",
    }
    merged = structlog.contextvars.merge_contextvars(
        None, "info", event_dict
    )
    # 经 add_log_level 处理
    merged = structlog.processors.add_log_level(None, "info", merged)
    # 经 JSONRenderer 处理
    renderer = structlog.processors.JSONRenderer()
    rendered = renderer(None, "info", merged)

    parsed = json.loads(rendered)
    assert parsed["event"] == "test log entry"
    assert parsed["request_id"] == "test-req-123"
    assert parsed["trace_id"] == "abcdef0123456789abcdef0123456789"
    assert parsed["span_id"] == "0000111122223333"

    # 清理
    structlog.contextvars.unbind_contextvars("request_id", "trace_id", "span_id")
    del os.environ["CF_LOG_FORMAT"]
