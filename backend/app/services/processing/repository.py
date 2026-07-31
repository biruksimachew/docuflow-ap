from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from app.db.database import engine


class DocumentNotProcessableError(RuntimeError):
    """Raised when a document cannot begin another processing attempt."""


async def start_processing_run(
    document_id: str,
) -> dict[str, Any]:
    run_id = str(uuid4())

    update_document = text(
        """
        update public.documents
        set
            processing_attempts = processing_attempts + 1,
            status = 'PREPROCESSING',
            processing_started_at = now(),
            processing_completed_at = null,
            last_error_code = null,
            last_error_message = null
        where
            id = cast(:document_id as uuid)
            and status in (
                'RECEIVED',
                'RETRY_SCHEDULED',
                'FAILED'
            )
        returning
            id,
            processing_attempts,
            storage_bucket,
            storage_object_key,
            detected_media_type,
            original_filename
        """
    )

    insert_run = text(
        """
        insert into public.processing_runs (
            id,
            document_id,
            attempt_number,
            status
        )
        values (
            cast(:run_id as uuid),
            cast(:document_id as uuid),
            :attempt_number,
            'STARTED'
        )
        """
    )

    set_latest_run = text(
        """
        update public.documents
        set last_processing_run_id =
            cast(:run_id as uuid)
        where id = cast(:document_id as uuid)
        """
    )

    insert_audit = text(
        """
        insert into public.audit_events (
            document_id,
            event_type,
            actor_type,
            reason,
            payload
        )
        values (
            cast(:document_id as uuid),
            'DOCUMENT_PREPROCESSING_STARTED',
            'SYSTEM',
            'Document preprocessing started.',
            cast(:payload as jsonb)
        )
        """
    )

    async with engine.begin() as connection:
        result = await connection.execute(
            update_document,
            {
                "document_id": document_id,
            },
        )

        document = result.mappings().one_or_none()

        if document is None:
            raise DocumentNotProcessableError(
                "The document is not in a processable status."
            )

        attempt_number = int(
            document["processing_attempts"]
        )

        await connection.execute(
            insert_run,
            {
                "run_id": run_id,
                "document_id": document_id,
                "attempt_number": attempt_number,
            },
        )

        await connection.execute(
            set_latest_run,
            {
                "run_id": run_id,
                "document_id": document_id,
            },
        )

        await connection.execute(
            insert_audit,
            {
                "document_id": document_id,
                "payload": json.dumps(
                    {
                        "processing_run_id": run_id,
                        "attempt_number": attempt_number,
                    }
                ),
            },
        )

    return {
        **dict(document),
        "processing_run_id": run_id,
        "attempt_number": attempt_number,
    }


async def set_document_status(
    *,
    document_id: str,
    status: str,
    event_type: str,
    reason: str | None,
    payload: dict[str, Any],
) -> None:
    update_document = text(
        """
        update public.documents
        set status = :status
        where id = cast(:document_id as uuid)
        """
    )

    insert_audit = text(
        """
        insert into public.audit_events (
            document_id,
            event_type,
            actor_type,
            reason,
            payload
        )
        values (
            cast(:document_id as uuid),
            :event_type,
            'SYSTEM',
            :reason,
            cast(:payload as jsonb)
        )
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            update_document,
            {
                "document_id": document_id,
                "status": status,
            },
        )

        await connection.execute(
            insert_audit,
            {
                "document_id": document_id,
                "event_type": event_type,
                "reason": reason,
                "payload": json.dumps(payload),
            },
        )


async def create_document_page(
    *,
    processing_run_id: str,
    document_id: str,
    page_number: int,
    original_storage_bucket: str,
    original_storage_object_key: str,
    processed_storage_bucket: str,
    processed_storage_object_key: str,
    width_px: int,
    height_px: int,
    preprocessing_operations: list[dict[str, Any]],
) -> dict[str, Any]:
    query = text(
        """
        insert into public.document_pages (
            processing_run_id,
            document_id,
            page_number,
            original_storage_bucket,
            original_storage_object_key,
            processed_storage_bucket,
            processed_storage_object_key,
            width_px,
            height_px,
            preprocessing_operations
        )
        values (
            cast(:processing_run_id as uuid),
            cast(:document_id as uuid),
            :page_number,
            :original_storage_bucket,
            :original_storage_object_key,
            :processed_storage_bucket,
            :processed_storage_object_key,
            :width_px,
            :height_px,
            cast(:preprocessing_operations as jsonb)
        )
        returning
            id,
            page_number,
            width_px,
            height_px
        """
    )

    async with engine.begin() as connection:
        result = await connection.execute(
            query,
            {
                "processing_run_id": processing_run_id,
                "document_id": document_id,
                "page_number": page_number,
                "original_storage_bucket": original_storage_bucket,
                "original_storage_object_key": original_storage_object_key,
                "processed_storage_bucket": processed_storage_bucket,
                "processed_storage_object_key": processed_storage_object_key,
                "width_px": width_px,
                "height_px": height_px,
                "preprocessing_operations": json.dumps(
                    preprocessing_operations
                ),
            },
        )

        row = result.mappings().one()

    return dict(row)


async def create_ocr_run(
    *,
    processing_run_id: str,
    document_id: str,
    provider: str,
    provider_version: str,
    language: str,
) -> str:
    ocr_run_id = str(uuid4())

    query = text(
        """
        insert into public.ocr_runs (
            id,
            processing_run_id,
            document_id,
            provider,
            provider_version,
            language,
            status
        )
        values (
            cast(:ocr_run_id as uuid),
            cast(:processing_run_id as uuid),
            cast(:document_id as uuid),
            :provider,
            :provider_version,
            :language,
            'STARTED'
        )
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            query,
            {
                "ocr_run_id": ocr_run_id,
                "processing_run_id": processing_run_id,
                "document_id": document_id,
                "provider": provider,
                "provider_version": provider_version,
                "language": language,
            },
        )

    return ocr_run_id


async def save_ocr_page_result(
    *,
    ocr_run_id: str,
    document_page_id: str,
    page_number: int,
    raw_text: str,
    average_confidence: float | None,
    tokens: list[dict[str, Any]],
) -> None:
    query = text(
        """
        insert into public.ocr_page_results (
            ocr_run_id,
            document_page_id,
            page_number,
            raw_text,
            average_confidence,
            tokens
        )
        values (
            cast(:ocr_run_id as uuid),
            cast(:document_page_id as uuid),
            :page_number,
            :raw_text,
            :average_confidence,
            cast(:tokens as jsonb)
        )
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            query,
            {
                "ocr_run_id": ocr_run_id,
                "document_page_id": document_page_id,
                "page_number": page_number,
                "raw_text": raw_text,
                "average_confidence": average_confidence,
                "tokens": json.dumps(tokens),
            },
        )


async def complete_ocr_run(
    ocr_run_id: str,
) -> None:
    query = text(
        """
        update public.ocr_runs
        set
            status = 'SUCCEEDED',
            completed_at = now(),
            error_code = null,
            error_message = null
        where id = cast(:ocr_run_id as uuid)
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            query,
            {
                "ocr_run_id": ocr_run_id,
            },
        )


async def complete_processing_run(
    *,
    processing_run_id: str,
    document_id: str,
) -> None:
    complete_run = text(
        """
        update public.processing_runs
        set
            status = 'SUCCEEDED',
            completed_at = now(),
            error_code = null,
            error_message = null
        where id = cast(:processing_run_id as uuid)
        """
    )

    complete_document = text(
        """
        update public.documents
        set
            processing_completed_at = now(),
            last_error_code = null,
            last_error_message = null
        where id = cast(:document_id as uuid)
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            complete_run,
            {
                "processing_run_id": processing_run_id,
            },
        )

        await connection.execute(
            complete_document,
            {
                "document_id": document_id,
            },
        )


async def fail_processing_run(
    *,
    processing_run_id: str,
    error_code: str,
    error_message: str,
) -> None:
    fail_processing = text(
        """
        update public.processing_runs
        set
            status = 'FAILED',
            completed_at = now(),
            error_code = :error_code,
            error_message = :error_message
        where id = cast(:processing_run_id as uuid)
        """
    )

    fail_ocr = text(
        """
        update public.ocr_runs
        set
            status = 'FAILED',
            completed_at = now(),
            error_code = :error_code,
            error_message = :error_message
        where
            processing_run_id =
                cast(:processing_run_id as uuid)
            and status = 'STARTED'
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            fail_processing,
            {
                "processing_run_id": processing_run_id,
                "error_code": error_code,
                "error_message": error_message,
            },
        )

        await connection.execute(
            fail_ocr,
            {
                "processing_run_id": processing_run_id,
                "error_code": error_code,
                "error_message": error_message,
            },
        )


async def mark_document_retry_scheduled(
    *,
    document_id: str,
    error_code: str,
    error_message: str,
    retry_number: int,
) -> None:
    update_document = text(
        """
        update public.documents
        set
            status = 'RETRY_SCHEDULED',
            last_error_code = :error_code,
            last_error_message = :error_message
        where id = cast(:document_id as uuid)
        """
    )

    insert_audit = text(
        """
        insert into public.audit_events (
            document_id,
            event_type,
            actor_type,
            reason,
            payload
        )
        values (
            cast(:document_id as uuid),
            'DOCUMENT_RETRY_SCHEDULED',
            'SYSTEM',
            :reason,
            cast(:payload as jsonb)
        )
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            update_document,
            {
                "document_id": document_id,
                "error_code": error_code,
                "error_message": error_message,
            },
        )

        await connection.execute(
            insert_audit,
            {
                "document_id": document_id,
                "reason": error_message,
                "payload": json.dumps(
                    {
                        "error_code": error_code,
                        "retry_number": retry_number,
                    }
                ),
            },
        )


async def mark_document_failed(
    *,
    document_id: str,
    error_code: str,
    error_message: str,
) -> None:
    update_document = text(
        """
        update public.documents
        set
            status = 'FAILED',
            processing_completed_at = now(),
            last_error_code = :error_code,
            last_error_message = :error_message
        where id = cast(:document_id as uuid)
        """
    )

    insert_audit = text(
        """
        insert into public.audit_events (
            document_id,
            event_type,
            actor_type,
            reason,
            payload
        )
        values (
            cast(:document_id as uuid),
            'DOCUMENT_PROCESSING_FAILED',
            'SYSTEM',
            :reason,
            cast(:payload as jsonb)
        )
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            update_document,
            {
                "document_id": document_id,
                "error_code": error_code,
                "error_message": error_message,
            },
        )

        await connection.execute(
            insert_audit,
            {
                "document_id": document_id,
                "reason": error_message,
                "payload": json.dumps(
                    {
                        "error_code": error_code,
                    }
                ),
            },
        )


async def mark_dispatch_failure(
    *,
    document_id: str,
    error_message: str,
) -> None:
    await mark_document_retry_scheduled(
        document_id=document_id,
        error_code="PROCESSING_QUEUE_UNAVAILABLE",
        error_message=error_message,
        retry_number=0,
    )


async def get_processing_snapshot(
    document_id: str,
) -> dict[str, Any] | None:
    document_query = text(
        """
        select
            id,
            status,
            original_filename,
            detected_media_type,
            page_count,
            sha256,
            processing_attempts,
            processing_started_at,
            processing_completed_at,
            last_error_code,
            last_error_message,
            created_at,
            updated_at
        from public.documents
        where id = cast(:document_id as uuid)
        """
    )

    run_query = text(
        """
        select
            id,
            attempt_number,
            status,
            error_code,
            error_message,
            started_at,
            completed_at
        from public.processing_runs
        where document_id =
            cast(:document_id as uuid)
        order by attempt_number desc
        limit 1
        """
    )

    pages_query = text(
        """
        select
            id,
            page_number,
            original_storage_bucket,
            original_storage_object_key,
            processed_storage_bucket,
            processed_storage_object_key,
            width_px,
            height_px,
            preprocessing_operations,
            created_at
        from public.document_pages
        where processing_run_id =
            cast(:processing_run_id as uuid)
        order by page_number
        """
    )

    ocr_run_query = text(
        """
        select
            id,
            provider,
            provider_version,
            language,
            status,
            error_code,
            error_message,
            started_at,
            completed_at
        from public.ocr_runs
        where processing_run_id =
            cast(:processing_run_id as uuid)
        limit 1
        """
    )

    results_query = text(
        """
        select
            result.id,
            result.page_number,
            result.raw_text,
            result.average_confidence,
            result.tokens,
            result.created_at
        from public.ocr_page_results result
        where result.ocr_run_id =
            cast(:ocr_run_id as uuid)
        order by result.page_number
        """
    )

    async with engine.connect() as connection:
        document_result = await connection.execute(
            document_query,
            {
                "document_id": document_id,
            },
        )

        document = document_result.mappings().one_or_none()

        if document is None:
            return None

        run_result = await connection.execute(
            run_query,
            {
                "document_id": document_id,
            },
        )

        latest_run = run_result.mappings().one_or_none()

        pages: list[dict[str, Any]] = []
        ocr_run: dict[str, Any] | None = None
        ocr_results: list[dict[str, Any]] = []

        if latest_run is not None:
            pages_result = await connection.execute(
                pages_query,
                {
                    "processing_run_id": str(
                        latest_run["id"]
                    ),
                },
            )

            pages = [
                dict(row)
                for row in pages_result.mappings().all()
            ]

            ocr_run_result = await connection.execute(
                ocr_run_query,
                {
                    "processing_run_id": str(
                        latest_run["id"]
                    ),
                },
            )

            ocr_run_row = (
                ocr_run_result.mappings().one_or_none()
            )

            if ocr_run_row is not None:
                ocr_run = dict(ocr_run_row)

                page_results = await connection.execute(
                    results_query,
                    {
                        "ocr_run_id": str(
                            ocr_run_row["id"]
                        ),
                    },
                )

                ocr_results = [
                    dict(row)
                    for row in page_results.mappings().all()
                ]

    return {
        "document": dict(document),
        "latest_processing_run": (
            dict(latest_run)
            if latest_run is not None
            else None
        ),
        "pages": pages,
        "ocr_run": ocr_run,
        "ocr_page_results": ocr_results,
    }