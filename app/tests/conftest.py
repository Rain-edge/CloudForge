"""pytest 夹具 — 提供隔离的 FastAPI 客户端与内存数据库。

测试隔离：每测试独立的 SQLite 内存库 + 重写 get_db 依赖 + ASGITransport 不走网络。
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.main import app
from app.models.task import Base


@pytest_asyncio.fixture
async def async_session():
    """每测试一个独立 SQLite 内存库。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield async_session_factory

    await engine.dispose()


@pytest_asyncio.fixture
async def client(async_session):
    """直接调用 ASGI 的异步 HTTP 客户端，依赖注入指向测试库。"""
    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()
