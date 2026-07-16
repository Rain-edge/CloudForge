import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_metrics_ok(client: AsyncClient):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert resp.text, "metrics body should not be empty"


@pytest.mark.asyncio
async def test_metrics_has_required_families(client: AsyncClient):
    resp = await client.get("/metrics")
    body = resp.text
    required = [
        "http_requests_total",
        "http_request_duration_seconds_bucket",
        "cloudforge_tasks_total",
        "cloudforge_db_pool_size",
        "cloudforge_app_info",
    ]
    for family in required:
        assert family in body, f"metric family '{family}' should be present"


@pytest.mark.asyncio
async def test_metrics_40plus_lines(client: AsyncClient):
    resp = await client.get("/metrics")
    lines = [l for l in resp.text.strip().split("\n") if l and not l.startswith("#")]
    assert len(lines) >= 40, f"expected >= 40 metric lines, got {len(lines)}"
