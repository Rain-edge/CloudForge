"""
pytest 测试夹具 — 为所有测试提供隔离的 FastAPI 客户端和内存数据库。
===========================================================================
本文件配置了 pytest 的两个核心 fixture：

  - async_session：提供 SQLite 内存数据库会话（不依赖外部 PostgreSQL）
  - client：提供 httpx AsyncClient（可以直接 await client.get("/health") 调用 API）

测试隔离策略：
  1. 每个测试函数使用独立的 SQLite 内存数据库（`sqlite+aiosqlite://`）
  2. 重写 get_db 依赖注入 — 把真实的 PostgreSQL 连接替换为测试数据库
  3. 自动建表和拆表（create_all / drop_all）
  4. 通过 httpx ASGITransport 而不是真实 HTTP 连接（更快、更可靠）

关于 httpx ASGITransport vs TestClient：
  - Starlette TestClient（同步）已过时，httpx ASGITransport（异步）是推荐做法
  - 好处：可以在同一测试中发送多个并发请求，模拟真实异步场景
"""
import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.main import app
from app.models.task import Base


# ── Fixture: 内存数据库会话 ───────────────────────────────
@pytest_asyncio.fixture
async def async_session():
    """为每个测试提供独立的 SQLite 内存数据库。

    SQLite 内存模式：
      sqlite+aiosqlite:///:memory:  → 每个连接都有独立的内存数据库
      使用 StaticPool 固定连接 → 确保所有操作看到同一份数据
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,            # 测试中通常不打印 SQL（调试时改为 True）
    )
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # 在每个测试开始前创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # yield 之前的代码 = setup，之后的代码 = teardown
    yield async_session_factory

    # 测试结束后清理
    await engine.dispose()


# ── Fixture: HTTP 客户端 ──────────────────────────────────
@pytest_asyncio.fixture
async def client(async_session):
    """为每个测试提供 httpx AsyncClient，直接调用 FastAPI ASGI 应用。

    关键步骤：
      app.dependency_overrides[get_db] → 用测试数据库替换真实 PostgreSQL 连接
      transport=ASGITransport(app=app)  → 不走网络，直接调用 ASGI 接口
      base_url="http://test"           → 必须有 base_url，否则 httpx 认为是相对 URL
    """
    # 重写依赖注入：所有需要 get_db 的路由函数都使用测试数据库
    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # 创建异步 HTTP 客户端（与 FastAPI 内部共享事件循环）
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    # 清理：移除依赖重写，避免污染其他测试
    app.dependency_overrides.clear()
