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

    public_api_base_url: str = (
        "http://127.0.0.1:8000"
    )

    notification_max_attempts: int = 3
    notification_retry_base_seconds: int = 2
    notification_retry_max_seconds: int = 300
    notification_delivery_stale_seconds: int = 60

    notification_webhook_timeout_seconds: int = 10
    notification_webhook_signing_secret: str = (
        "docuflow-local-notification-secret"
    )
    notification_webhook_allowed_hosts: str = (
        "api,localhost,127.0.0.1"
    )

    notification_email_provider: str = (
        "LOCAL_SINK"
    )
    notification_email_from: str = (
        "docuflow@localhost.test"
    )

    notification_smtp_host: str = (
        "host.docker.internal"
    )
    notification_smtp_port: int = 1025
    notification_smtp_timeout_seconds: int = 10
    notification_smtp_username: str = ""
    notification_smtp_password: str = ""
    notification_smtp_starttls: bool = False

    @property
    def notification_webhook_allowed_host_set(
        self,
    ) -> set[str]:
        return {
            value.strip().lower()
            for value in (
                self
                .notification_webhook_allowed_hosts
                .split(",")
            )
            if value.strip()
        }

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