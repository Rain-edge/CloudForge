"""CloudForge 应用入口 — 创建 FastAPI 实例并组装可观测性三支柱。

组装顺序重要：telemetry（创建 Span）→ RequestID 中间件（读 Span）→ metrics → 路由。
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.core.database import engine
from app.core.metrics import setup_metrics
from app.core.telemetry import setup_telemetry
from app.middleware.logging import RequestIDMiddleware
from app.models import Base  # noqa: F401  确保所有 ORM 模型被导入注册
from app.routers import health, tasks


@asynccontextmanager
async def lifespan(application: FastAPI):
    """启动时等待 PG 就绪并建表，关闭时释放连接池。"""
    # depends_on 仅保证容器启动，PG 可能仍在 crash recovery，故二次重试
    max_retries = 10
    for attempt in range(1, max_retries + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            break
        except Exception:
            if attempt == max_retries:
                raise
            await asyncio.sleep(2)

    # 演示环境直接建表；生产应使用 alembic upgrade head
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    await engine.dispose()


app = FastAPI(
    title="CloudForge",
    description="Cloud-native microservice operations platform",
    version="0.1.0",
    lifespan=lifespan,
)

# 顺序：先创建 Span，中间件才能读取 trace_id
setup_telemetry(app)
app.add_middleware(RequestIDMiddleware)
setup_metrics(app)

app.include_router(health.router)
app.include_router(tasks.router)
