"""
异步数据库引擎与会话工厂 — SQLAlchemy 2.0 异步风格。
===========================================================
本文件负责：
  1. 创建 asyncpg 驱动的异步引擎（连接池由 SQLAlchemy QueuePool 管理）
  2. 提供 async_sessionmaker 工厂函数
  3. 导出 get_db 依赖注入函数（FastAPI Depends 使用）

关键概念：
  - AsyncSession：异步数据库会话，替代同步 Session
  - expire_on_commit=False：提交后不刷新 ORM 对象，避免惰性加载导致的异常
  - get_db 作为 FastAPI Depends：每个请求自动创建/关闭会话

连接池配置（解决"跨调用 PostgreSQL 进程丢失"问题）：
  - pool_pre_ping=True：每次从池中检出连接前先执行 SELECT 1 验证有效性，
    防止使用已被 PostgreSQL 服务端关闭的 stale 连接（如 PG 重启、空闲超时断开）
  - pool_size=10：核心连接数（常驻池中）
  - max_overflow=20：超出 pool_size 后可临时创建的额外连接数（峰值 30）
  - pool_recycle=3600：连接存活超过 1 小时后自动回收，防止防火墙/NAT/负载均衡器
    静默断开空闲连接
  - connect_args：asyncpg 级超时参数，防止网络抖动时连接卡死
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# 异步引擎 — 连接池自动管理，生产级参数
engine = create_async_engine(
    settings.database_url,
    echo=False,
    # ── 连接池配置 ──────────────────────────────────────
    pool_pre_ping=True,       # 检出前验证连接有效性（核心修复）
    pool_size=10,             # 常驻连接数
    max_overflow=20,          # 峰值额外连接数（最大 10+20=30）
    pool_recycle=3600,        # 1 小时后强制回收连接（防止中间网络设备断连）
    # ── asyncpg 驱动级超时 ─────────────────────────────
    connect_args={
        "timeout": 10,            # 建立新连接的超时秒数
        "command_timeout": 30,    # 单条 SQL 命令执行超时秒数
    },
)

# 会话工厂 — 每次调用 async_session() 创建一个新的数据库会话
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ── FastAPI 依赖注入 ──────────────────────────────────────
# 使用方式：在路径操作函数中声明 db: AsyncSession = Depends(get_db)
# FastAPI 会在请求进入时调用 get_db()，响应返回后自动关闭会话。
async def get_db() -> AsyncSession:  # type: ignore[misc]
    """为每个 HTTP 请求提供独立的数据库会话。"""
    async with async_session() as session:
        yield session
