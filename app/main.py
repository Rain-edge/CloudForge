"""
CloudForge — 云原生微服务运维平台入口。
============================================
本文件负责：
  1. 创建 FastAPI 应用实例（带生命周期管理）
  2. 注册中间件（请求 ID 注入、结构化日志）
  3. 注册路由（健康检查、Task CRUD）
  4. 初始化可观测性三大支柱（Logging ↔ Metrics ↔ Tracing）
  5. 启动时自动建表（演示环境，生产请用 alembic 迁移）
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.database import engine
from app.core.metrics import setup_metrics
from app.core.telemetry import setup_telemetry
from app.middleware.logging import RequestIDMiddleware
from app.models import Base  # noqa: F401  — 确保所有 ORM 模型被导入/注册
from app.routers import health, tasks


# ── 生命周期 ──────────────────────────────────────────────
# FastAPI 的 lifespan 取代了旧的 on_event("startup") / on_event("shutdown")。
# 启动阶段：创建数据库表（仅演示用）；关闭阶段：释放引擎连接池。
@asynccontextmanager
async def lifespan(application: FastAPI):
    """应用生命周期：启动时建表，关闭时释放数据库连接池。"""
    # 启动：自动创建所有 ORM 模型对应的表（演示环境做法）
    # 生产环境应使用 alembic upgrade head 管理数据库迁移
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # 关闭：释放异步数据库引擎的连接池
    await engine.dispose()


# ── 应用工厂 ──────────────────────────────────────────────
# 将 app 创建封装为函数，方便测试时创建独立实例。
app = FastAPI(
    title="CloudForge",
    description="Cloud‑native microservice operations platform",
    version="0.1.0",
    lifespan=lifespan,
)

# ── 可观测性（顺序重要：先 Marker，再中间件，再路由） ─────
# OpenTelemetry：自动为 FastAPI 路由和 SQLAlchemy 查询生成 Trace
setup_telemetry(app)

# Request ID 中间件：从 X-Request-ID 请求头读取/生成唯一 ID，
# 并注入 structlog + trace_id，实现请求全链路追踪。
app.add_middleware(RequestIDMiddleware)

# Prometheus 指标：在 /metrics 端点暴露 HTTP 请求计数、延迟等
setup_metrics(app)

# ── 路由注册 ──────────────────────────────────────────────
app.include_router(health.router)   # GET /health — 健康检查
app.include_router(tasks.router)    # CRUD /tasks — 任务管理 API
