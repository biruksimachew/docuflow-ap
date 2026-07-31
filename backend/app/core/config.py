from decimal import Decimal
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

    max_upload_size_mb: int = 20
    max_document_pages: int = 30

    allowed_file_types: str = (
        "application/pdf,image/jpeg,image/png"
    )

    allowed_currencies: str = "USD"

    validation_currency_tolerance: Decimal = Decimal(
        "0.01"
    )

    invoice_future_tolerance_days: int = 7

    s3_endpoint_url: str = "http://minio:9000"
    s3_access_key: str = "docuflow"
    s3_secret_key: str = "docuflow-local-secret"
    s3_region: str = "us-east-1"

    s3_bucket_source_invoices: str = "source-invoices"
    s3_bucket_derived_pages: str = "derived-pages"

    ocr_provider: str = "tesseract"
    ocr_language: str = "eng"
    ocr_task_max_retries: int = 2

    pdf_render_dpi: int = 200

    @property
    def allowed_file_type_set(self) -> set[str]:
        return {
            value.strip().lower()
            for value in self.allowed_file_types.split(",")
            if value.strip()
        }

    @property
    def allowed_currency_set(self) -> set[str]:
        return {
            value.strip().upper()
            for value in self.allowed_currencies.split(",")
            if value.strip()
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()