"""结构化日志测试 — 验证应用真实使用的 structlog 配置输出 JSON 且带 trace 关联字段。

与旧版"测试里自己 configure + 硬编码 trace_id"不同，
这里直接调用 app.core.logging.setup_logging()（应用启动时实际使用的函数），
并通过 structlog.contextvars 模拟 RequestIDMiddleware 的绑定行为。
"""

import json

import pytest
import structlog


def test_json_log_format_outputs_trace_fields(capsys):
    """CF_LOG_FORMAT=json 时，日志为合法 JSON 且含 request_id/trace_id/span_id。"""
    from app.core.logging import setup_logging

    setup_logging(log_format="json")

    # 模拟 RequestIDMiddleware 的绑定行为（middleware/logging.py 中同款字段）
    structlog.contextvars.bind_contextvars(
        request_id="test-req-123",
        trace_id="abcdef0123456789abcdef0123456789",
        span_id="0000111122223333",
    )

    structlog.get_logger().info("health check passed")
    captured = capsys.readouterr().out

    # 取最后一行（structlog 一行一条日志）
    parsed = json.loads(captured.strip().splitlines()[-1])
    assert parsed["event"] == "health check passed"
    assert parsed["level"] == "info"
    assert parsed["request_id"] == "test-req-123"
    assert parsed["trace_id"] == "abcdef0123456789abcdef0123456789"
    assert parsed["span_id"] == "0000111122223333"

    structlog.contextvars.unbind_contextvars("request_id", "trace_id", "span_id")


def test_console_log_format_not_json(capsys):
    """CF_LOG_FORMAT=console 时输出可读 key-value 格式（本地开发）。"""
    from app.core.logging import setup_logging

    setup_logging(log_format="console")

    structlog.get_logger().info("hello console")
    captured = capsys.readouterr().out

    # console 格式是人类可读文本（时间戳 + 级别 + 事件），不是 JSON
    assert "hello console" in captured
    with pytest.raises(json.JSONDecodeError):
        json.loads(captured.strip())
