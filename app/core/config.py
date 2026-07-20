"""
应用配置 — 使用 pydantic-settings 统一管理所有环境变量。
配置优先级（由低到高）：
  1. 代码中的 default 值
  2. 项目根目录的 .env 文件（如果存在）
  3. 操作系统环境变量（最高优先级）

所有环境变量使用 CF_ 前缀避免与系统变量冲突：
  CF_DATABASE_URL, CF_REDIS_URL, CF_SECRET_KEY, CF_LOG_LEVEL

用法：
  from app.core.config import settings
  print(settings.database_url)
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """全局单例配置。字段名自动映射为大写 + CF_ 前缀的环境变量。"""

    # PostgreSQL 连接字符串，驱动使用 asyncpg（异步高性能）
    database_url: str = (
        "postgresql+asyncpg://cloudforge:cloudforge@localhost:5432/cloudforge"
    )

    # Redis 连接字符串（当前仅预留，Celery 异步任务队列后续接入）
    redis_url: str = "redis://localhost:6379/0"

    # JWT 签名密钥（后续实现鉴权时使用，当前仅预留）
    # 生产环境必须替换为随机长字符串
    secret_key: str = "change-me-in-production"

    # structlog 日志级别：DEBUG / INFO / WARNING / ERROR
    log_level: str = "INFO"

    # pydantic-settings 配置：
    #   env_prefix="CF_"   → database_url 映射为环境变量 CF_DATABASE_URL
    #   env_file=".env"    → 自动加载项目根目录的 .env 文件
    model_config = {"env_prefix": "CF_", "env_file": ".env"}


# 模块级单例 — 进程内全局共享同一个配置对象
settings = Settings()
