from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://cloudforge:cloudforge@localhost:5432/cloudforge"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-in-production"
    log_level: str = "INFO"

    model_config = {"env_prefix": "CF_", "env_file": ".env"}


settings = Settings()
