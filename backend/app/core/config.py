from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "DocuFlow AP"
    app_env: str = "local"
    app_debug: bool = True

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@"
        "host.docker.internal:54322/postgres"
    )

    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
