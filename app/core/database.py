"""
异步数据库引擎与会话工厂 — SQLAlchemy 2.0 异步风格。
===========================================================
本文件负责：
  1. 创建 asyncpg 驱动的异步引擎（连接池大小由 SQLAlchemy 默认管理）
  2. 提供 async_sessionmaker 工厂函数
  3. 导出 get_db 依赖注入函数（FastAPI Depends 使用）

关键概念：
  - AsyncSession：异步数据库会话，替代同步 Session
  - expire_on_commit=False：提交后不刷新 ORM 对象，避免惰性加载导致的异常
  - get_db 作为 FastAPI Depends：每个请求自动创建/关闭会话
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# 异步引擎 — 连接池自动管理
# echo=False：不打印 SQL（调试时设为 True 查看实际 SQL）
engine = create_async_engine(settings.database_url, echo=False)

# 会话工厂 — 每次调用 async_session() 创建一个新的数据库会话
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ── FastAPI 依赖注入 ──────────────────────────────────────
# 使用方式：在路径操作函数中声明 db: AsyncSession = Depends(get_db)
# FastAPI 会在请求进入时调用 get_db()，响应返回后自动关闭会话。
async def get_db() -> AsyncSession:  # type: ignore[misc]
    """为每个 HTTP 请求提供独立的数据库会话。"""
    async with async_session() as session:
        yield session
