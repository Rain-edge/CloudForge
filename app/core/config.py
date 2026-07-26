"""应用配置 — 基于 pydantic-settings 的单一配置源。

环境变量优先级（低→高）：代码默认值 < .env 文件 < OS 环境变量。
所有变量统一使用 CF_ 前缀（如 CF_DATABASE_URL），避免与系统变量冲突。
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """全局配置，字段名自动映射为 CF_ 前缀的大写环境变量。"""

    # asyncpg 异步驱动
    database_url: str = (
        "postgresql+asyncpg://cloudforge:cloudforge@localhost:5432/cloudforge"
    )
    # 预留：后续接入 Celery 异步任务队列
    redis_url: str = "redis://localhost:6379/0"
    # JWT 签名密钥，生产环境必须替换为随机长字符串
    secret_key: str = "change-me-in-production"
    # structlog 日志级别
    log_level: str = "INFO"

    model_config = {"env_prefix": "CF_", "env_file": ".env"}


# 进程级单例，避免重复加载配置
settings = Settings()
