"""/metrics 端点测试 — 验证 Prometheus 自动生成的标准指标可用。"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_metrics_ok(client: AsyncClient):
    """端点返回 200 且非空。"""
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert resp.text, "metrics body should not be empty"


@pytest.mark.asyncio
async def test_metrics_has_required_families(client: AsyncClient):
    """包含自动生成的 http_requests_total 与延迟直方图。"""
    resp = await client.get("/metrics")
    body = resp.text

    required = [
        "http_requests_total",
        "http_request_duration_seconds_bucket",
    ]
    for family in required:
        assert family in body, f"metric family '{family}' should be present"


@pytest.mark.asyncio
async def test_metrics_40plus_lines(client: AsyncClient):
    """指标行数 ≥ 40，确保采集正常。"""
    resp = await client.get("/metrics")
    lines = [
        l for l in resp.text.strip().split("\n") if l and not l.startswith("#")
    ]
    assert len(lines) >= 40, f"expected >= 40 metric lines, got {len(lines)}"
