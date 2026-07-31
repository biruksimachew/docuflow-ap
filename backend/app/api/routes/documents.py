from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from anyio import to_thread
from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)

from app.core.config import settings
from app.schemas.documents import DocumentUploadResponse
from app.services.intake.repository import (
    create_document,
    find_document_by_sha256,
    record_duplicate_intake,
)
from app.services.intake.storage import get_object_storage
from app.services.intake.validation import (
    FileValidationError,
    validate_upload,
)
from app.services.processing.repository import (
    get_processing_snapshot,
    mark_dispatch_failure,
)
from app.workers.tasks import process_document


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)

ALLOWED_SOURCE_CHANNELS = {
    "WEB_UPLOAD",
    "EMAIL",
    "BATCH_IMPORT",
}


async def read_bounded_upload(
    upload: UploadFile,
    maximum_size_bytes: int,
) -> bytes:
    buffer = bytearray()
    chunk_size = 1024 * 1024

    try:
        while True:
            chunk = await upload.read(chunk_size)

            if not chunk:
                break

            buffer.extend(chunk)

            if len(buffer) > maximum_size_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail={
                        "code": "FILE_SIZE_LIMIT_EXCEEDED",
                        "message": (
                            "The uploaded file exceeds the "
                            "configured size limit."
                        ),
                    },
                )
    finally:
        await upload.close()

    return bytes(buffer)


def build_response(
    row: dict,
    *,
    is_duplicate: bool,
    processing_enqueued: bool = False,
    processing_task_id: str | None = None,
) -> DocumentUploadResponse:
    return DocumentUploadResponse(
        document_id=row["id"],
        status=row["status"],
        is_duplicate=is_duplicate,
        processing_enqueued=processing_enqueued,
        processing_task_id=processing_task_id,
        original_filename=row["original_filename"],
        sanitized_filename=row["sanitized_filename"],
        detected_media_type=row["detected_media_type"],
        file_size_bytes=row["file_size_bytes"],
        page_count=row["page_count"],
        sha256=row["sha256"],
        quarantine_reason=row["quarantine_reason"],
        created_at=row["created_at"],
    )


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    response: Response,
    file: UploadFile = File(...),
    source_channel: str = Form(default="WEB_UPLOAD"),
    source_message_id: str | None = Form(default=None),
    source_attachment_id: str | None = Form(default=None),
) -> DocumentUploadResponse:
    normalized_source_channel = source_channel.strip().upper()

    if normalized_source_channel not in ALLOWED_SOURCE_CHANNELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "INVALID_SOURCE_CHANNEL",
                "message": (
                    "source_channel must be WEB_UPLOAD, "
                    "EMAIL, or BATCH_IMPORT."
                ),
            },
        )

    maximum_size_bytes = (
        settings.max_upload_size_mb * 1024 * 1024
    )

    content = await read_bounded_upload(
        file,
        maximum_size_bytes,
    )

    original_filename = file.filename or "invoice-upload"

    try:
        validated = validate_upload(
            content=content,
            original_filename=original_filename,
            declared_media_type=file.content_type,
            maximum_size_bytes=maximum_size_bytes,
            maximum_pages=settings.max_document_pages,
            allowed_media_types=settings.allowed_file_type_set,
        )
    except FileValidationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "code": exc.code,
                "message": exc.message,
            },
        ) from exc

    source_metadata = {
        "original_filename": original_filename,
        "declared_media_type": file.content_type,
    }

    existing_document = await find_document_by_sha256(
        validated.sha256
    )

    if existing_document is not None:
        await record_duplicate_intake(
            document_id=str(existing_document["id"]),
            source_channel=normalized_source_channel,
            source_message_id=source_message_id,
            source_attachment_id=source_attachment_id,
            source_metadata=source_metadata,
            sha256=validated.sha256,
        )

        response.status_code = status.HTTP_200_OK

        return build_response(
            existing_document,
            is_duplicate=True,
        )

    document_id = uuid4()

    date_path = datetime.now(
        timezone.utc
    ).strftime("%Y/%m/%d")

    object_key = (
        f"documents/{date_path}/"
        f"{document_id}/"
        f"{validated.sanitized_filename}"
    )

    object_storage = get_object_storage()

    try:
        await to_thread.run_sync(
            lambda: object_storage.put_source_document(
                object_key=object_key,
                content=validated.content,
                media_type=validated.detected_media_type,
                metadata={
                    "document-id": str(document_id),
                    "sha256": validated.sha256,
                    "source-channel": normalized_source_channel,
                },
            )
        )
    except Exception as exc:
        logger.exception(
            "Source document storage failed."
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "OBJECT_STORAGE_UNAVAILABLE",
                "message": (
                    "The source document could not be stored. "
                    "Retrying with the same file is safe."
                ),
            },
        ) from exc

    document_status = (
        "QUARANTINED"
        if validated.quarantine_reason
        else "RECEIVED"
    )

    try:
        row = await create_document(
            document_id=str(document_id),
            status=document_status,
            source_channel=normalized_source_channel,
            original_filename=validated.original_filename,
            sanitized_filename=validated.sanitized_filename,
            declared_media_type=validated.declared_media_type,
            detected_media_type=validated.detected_media_type,
            file_size_bytes=validated.file_size_bytes,
            page_count=validated.page_count,
            sha256=validated.sha256,
            storage_bucket=settings.s3_bucket_source_invoices,
            storage_object_key=object_key,
            quarantine_reason=validated.quarantine_reason,
            source_message_id=source_message_id,
            source_attachment_id=source_attachment_id,
            source_metadata=source_metadata,
        )
    except Exception:
        logger.exception(
            "Database intake transaction failed."
        )

        try:
            await to_thread.run_sync(
                lambda: object_storage.delete_source_document(
                    object_key=object_key
                )
            )
        except Exception:
            logger.exception(
                "Failed to clean up orphaned source object."
            )

        raise

    processing_task_id: str | None = None
    processing_enqueued = False

    if document_status == "RECEIVED":
        try:
            task = process_document.delay(
                str(document_id)
            )

            processing_task_id = task.id
            processing_enqueued = True
        except Exception as exc:
            logger.exception(
                "Document processing dispatch failed."
            )

            await mark_dispatch_failure(
                document_id=str(document_id),
                error_message=str(exc)[:2000],
            )

            row["status"] = "RETRY_SCHEDULED"

    return build_response(
        row,
        is_duplicate=False,
        processing_enqueued=processing_enqueued,
        processing_task_id=processing_task_id,
    )


@router.get(
    "/{document_id}/processing",
)
async def document_processing(
    document_id: UUID,
) -> dict:
    snapshot = await get_processing_snapshot(
        str(document_id)
    )

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "DOCUMENT_NOT_FOUND",
                "message": "The document does not exist.",
            },
        )

    return snapshot