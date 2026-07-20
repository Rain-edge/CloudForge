"""
Alembic 异步迁移环境 — 数据库 schema 版本管理。
=======================================================
本文件是 alembic 的"运行时环境"，负责：
  1. 加载项目配置（从 app.core.config.settings 读取数据库 URL）
  2. 导入 ORM 模型（让 autogenerate 自动检测 schema 变更）
  3. 提供在线/离线两种迁移模式

日常开发命令（在项目根目录执行）：
  # 生成新迁移（自动检测 ORM 模型变更）
  alembic revision --autogenerate -m "add user table"

  # 升级到最新版本
  alembic upgrade head

  # 回滚一个版本
  alembic downgrade -1

  # 查看当前版本
  alembic current

  # 查看迁移历史
  alembic history

注意：
  - 首次运行需要本地 PostgreSQL 可达（settings.database_url 中的地址）
  - SQLite 不支持 ALTER TABLE，autogenerate 的变更检测与 PostgreSQL 不完全一致
  - 不使用 alembic.ini 中的 sqlalchemy.url，而是从项目配置动态读取
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ── Alembic Config 对象（由命令行 -c 参数指定 .ini 文件）──
config = context.config

# ── 配置 Python 日志（读取 alembic.ini 中的 [loggers] 节）──
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── 导入 ORM 元数据（autogenerate 需要）──────────────────
# alembic autogenerate 对比 target_metadata 和数据库实际 schema 来生成迁移
from app.models.task import Base  # noqa: E402, F401

target_metadata = Base.metadata

# ── 从项目配置读取数据库 URL（覆盖 alembic.ini）─────────
# 好处：保持单一配置源（app.core.config.settings），避免 .ini 和 .env 重复
from app.core.config import settings  # noqa: E402

config.set_main_option("sqlalchemy.url", settings.database_url)


# ── 离线模式（生成 SQL 脚本，不连接数据库）───────────────
def run_migrations_offline() -> None:
    """离线迁移：输出 SQL 到文件而不是实际执行。

    用法：alembic upgrade head --sql > migration.sql
    适用场景：DBA 审查 SQL 后再手动执行
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ── 在线辅助函数 ──────────────────────────────────────────
def do_run_migrations(connection: Connection) -> None:
    """在给定的数据库连接上执行迁移。"""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


# ── 在线模式（连接数据库直接执行）─────────────────────────
async def run_async_migrations() -> None:
    """异步在线迁移：创建异步引擎并执行迁移。

    使用 NullPool 避免迁移期间的空闲连接问题。
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # 不保持连接池，迁移完成后即时释放
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """在线迁移入口（同步包装器）。"""
    asyncio.run(run_async_migrations())


# ── 执行 ──────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
