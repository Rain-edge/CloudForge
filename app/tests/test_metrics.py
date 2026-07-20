"""
Prometheus 指标端点测试 — 验证 /metrics 端点正常暴露。
============================================================
本文测试 /metrics 端点的以下方面：

  1. 端点可访问（返回 200）
  2. 包含自动生成的 http_requests_total 等标准指标
  3. 指标行数合理（≥ 40 行，确保采集正常工作）

注意：
  prometheus-fastapi-instrumentator 自动生成标准 HTTP 指标，
  自定义业务指标（如 cloudforge_tasks_total）需要额外开发并注册，
  当前未实现。
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_metrics_ok(client: AsyncClient):
    """验证 /metrics 端点返回 200 且内容非空。"""
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert resp.text, "metrics body should not be empty"


@pytest.mark.asyncio
async def test_metrics_has_required_families(client: AsyncClient):
    """验证 /metrics 包含了 prometheus-fastapi-instrumentator 自动生成的标准指标。

    自动生成的指标包括：
      - http_requests_total           (计数器：请求总数)
      - http_request_duration_seconds  (直方图：请求延迟)
      - http_request_size_bytes       (摘要：请求体大小)
    """
    resp = await client.get("/metrics")
    body = resp.text

    # 仅断言自动生成的标配指标，不检查未实现的自定义指标
    required = [
        "http_requests_total",
        "http_request_duration_seconds_bucket",
    ]
    for family in required:
        assert family in body, f"metric family '{family}' should be present"


@pytest.mark.asyncio
async def test_metrics_40plus_lines(client: AsyncClient):
    """验证 /metrics 至少产生 40 行数据（非注释行），确保采集正常工作。

    prometheus-fastapi-instrumentator 默认会生成直方图的多个桶，
    加上请求计数和摘要统计，总计远超 40 行。
    """
    resp = await client.get("/metrics")
    lines = [
        l for l in resp.text.strip().split("\n") if l and not l.startswith("#")
    ]
    assert len(lines) >= 40, f"expected >= 40 metric lines, got {len(lines)}"
