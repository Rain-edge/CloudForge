"""/health 端点测试。

health 直接用 async_session（非 get_db），会连真实 PG：
有 PG → 200，无 PG → 503，两者均合法。
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_ok(client: AsyncClient):
    """接受 200（健康）或 503（DB 不可达）两种合法结果。"""
    resp = await client.get("/health")

    assert resp.status_code in (200, 503)

    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert data["db"] in ("connected", "error")


@pytest.mark.asyncio
async def test_health_live_always_ok(client: AsyncClient):
    """/health/live 不依赖 DB，任何情况下都应返回 200（liveness 探针）。"""
    resp = await client.get("/health/live")

    assert resp.status_code == 200
    assert resp.json() == {"status": "alive"}
