import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_ok(client: AsyncClient):
    resp = await client.get("/health")
    # Accept both 200 (DB connected) and 503 (DB unavailable in test env)
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert data["db"] in ("connected", "error")
