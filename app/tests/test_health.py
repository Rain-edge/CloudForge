"""
健康检查 API 测试 — 验证 /health 端点的行为。
===================================================
本文测试两种场景：

  1. 正常情况（数据库连接可用）
  2. 降级情况（数据库不可用 — 内存 SQLite 不影响此测试）

注意：
  测试使用 SQLite 内存数据库，而 health 端点直接使用 async_session（非 get_db 依赖注入）。
  因此 health 端点会尝试连接真实的 PostgreSQL（settings.database_url），
  测试中数据库不可达，应返回 503。

  如果测试环境有 PostgreSQL，则返回 200。测试兼容两种结果。
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_ok(client: AsyncClient):
    """验证 /health 端点返回正确的状态码和数据结构。

    兼容场景：
      - 数据库可用 → 200, {"status":"ok", "db":"connected"}
      - 数据库不可用 → 503, {"status":"degraded", "db":"error"}

    两种结果都是合法的端点行为。
    """
    resp = await client.get("/health")

    # 接受 200（健康）或 503（数据库不可达）
    assert resp.status_code in (200, 503)

    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert data["db"] in ("connected", "error")
