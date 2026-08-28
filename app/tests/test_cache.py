"""Redis 缓存层测试 — 验证降级策略（测试环境无 Redis，必须安全降级）。"""

import pytest

from app.core import cache


@pytest.mark.asyncio
async def test_cache_get_tasks_returns_none_when_redis_down(monkeypatch):
    """Redis 不可达时读缓存返回 None，调用方应直读 DB。"""
    # 指向本机不可达端口，模拟 Redis 故障
    monkeypatch.setattr(cache.settings, "redis_url", "redis://127.0.0.1:1/0")
    monkeypatch.setattr(cache, "_client", None)

    assert await cache.cache_get_tasks() is None


@pytest.mark.asyncio
async def test_cache_invalidate_does_not_raise_when_redis_down(monkeypatch):
    """Redis 不可达时失效缓存不抛异常（写路径不被缓存拖垮）。"""
    monkeypatch.setattr(cache.settings, "redis_url", "redis://127.0.0.1:1/0")
    monkeypatch.setattr(cache, "_client", None)

    # 不应抛出异常
    await cache.cache_invalidate_tasks()
    await cache.cache_set_tasks([])


@pytest.mark.asyncio
async def test_list_tasks_works_without_redis(client):
    """Redis 不可达时 GET /tasks 正常返回（走降级直读 DB）。"""
    resp = await client.get("/tasks")

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
