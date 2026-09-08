"""异步数据库引擎与会话工厂（SQLAlchemy 2.0 async）。

提供 FastAPI 依赖注入用的 get_db()，每个请求获得独立会话并在响应后关闭。
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,   # 检出前验证连接，防止 PG 重启/空闲超时产生的 stale 连接
    pool_size=10,         # 常驻连接数
    max_overflow=20,      # 峰值可临时扩展至 30
    pool_recycle=3600,    # 1h 回收，避免 NAT/防火墙静默断连
    connect_args={
        "timeout": 10,        # 建连超时
        "command_timeout": 30,  # 单 SQL 超时
    },
)

# expire_on_commit=False：提交后不重新加载，避免异步惰性加载报错
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """FastAPI 依赖：为每个 HTTP 请求提供独立会话，响应后自动关闭。"""
    async with async_session() as session:
        yield session
