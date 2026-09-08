"""Redis 缓存层 — 任务列表缓存，带降级策略。

设计（对应简历"Redis 7"技术栈，真实可用的缓存逻辑）：
  - 读路径：GET /tasks 先查 Redis（key=cf:tasks:list，TTL 60s），
    命中直接返回（省一次 DB 查询）；miss 则查 PostgreSQL 并回填缓存
  - 写路径：create / update / delete 后删除缓存 key（write-through invalidate），
    下次读取重建，保证缓存与 DB 一致
  - 降级：Redis 不可达/超时 → 读返回 None（走 DB）、写静默忽略，
    缓存只是加速层，Redis 故障不影响功能（连接超时 1s，不拖慢请求）

一致性说明：写失效 + TTL 兜底（60s 后即使失效遗漏也会自动过期）。
热点 key 重建未加锁（演示场景可接受，面试可讨论 mutex 重建方案）。
"""
import json
import logging

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

TASKS_LIST_KEY = "cf:tasks:list"
TASKS_CACHE_TTL = 60  # 秒；TTL 兜底，防止失效遗漏导致数据长期陈旧

_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """懒创建 Redis 客户端；连接超时 1s，保证 Redis 故障时不拖慢请求。"""
    global _client
    if _client is None:
        _client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    return _client


async def cache_get_tasks() -> list | None:
    """读缓存；Redis 不可达返回 None（调用方改走 DB）。"""
    try:
        raw = await get_redis().get(TASKS_LIST_KEY)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        logger.warning("Redis 不可达，任务列表缓存降级为直读 DB")
        return None


async def cache_set_tasks(tasks: list) -> None:
    """回填缓存；失败静默（缓存是加速层，不影响主链路）。"""
    try:
        await get_redis().set(TASKS_LIST_KEY, json.dumps(tasks), ex=TASKS_CACHE_TTL)
    except Exception:
        pass


async def cache_invalidate_tasks() -> None:
    """写操作后失效缓存；失败静默（TTL 兜底）。"""
    try:
        await get_redis().delete(TASKS_LIST_KEY)
    except Exception:
        pass
