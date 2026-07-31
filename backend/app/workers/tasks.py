import asyncio
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.db.database import engine
from app.services.processing.pipeline import (
    DocumentProcessingError,
    process_document_pipeline,
)
from app.services.processing.repository import (
    mark_document_failed,
    mark_document_retry_scheduled,
)
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.ping")
def ping() -> dict[str, str]:
    """Small task used to verify worker communication."""

    return {
        "status": "pong",
        "worker": "docuflow-ap",
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
    }


async def _execute_processing_attempt(
    *,
    document_id: str,
    will_retry: bool,
    retry_number: int,
) -> dict[str, Any]:
    try:
        return await process_document_pipeline(
            document_id
        )
    except Exception as exc:
        error_code = getattr(
            exc,
            "code",
            type(exc).__name__,
        )

        error_message = str(exc)[:2000]

        if will_retry:
            await mark_document_retry_scheduled(
                document_id=document_id,
                error_code=error_code,
                error_message=error_message,
                retry_number=retry_number,
            )
        else:
            await mark_document_failed(
                document_id=document_id,
                error_code=error_code,
                error_message=error_message,
            )

        raise
    finally:
        await engine.dispose()


@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_document",
    max_retries=settings.ocr_task_max_retries,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_document(
    self,
    document_id: str,
) -> dict[str, Any]:
    retries_used = int(
        self.request.retries
    )

    will_retry = (
        retries_used < self.max_retries
    )

    try:
        return asyncio.run(
            _execute_processing_attempt(
                document_id=document_id,
                will_retry=will_retry,
                retry_number=retries_used + 1,
            )
        )
    except DocumentProcessingError as exc:
        if will_retry:
            countdown_seconds = (
                5 * (2 ** retries_used)
            )

            raise self.retry(
                exc=exc,
                countdown=countdown_seconds,
            )

        raise
    except Exception as exc:
        if will_retry:
            countdown_seconds = (
                5 * (2 ** retries_used)
            )

            raise self.retry(
                exc=exc,
                countdown=countdown_seconds,
            )

        raise