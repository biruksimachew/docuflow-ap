from __future__ import annotations

from dataclasses import asdict
from statistics import mean
from typing import Any

from anyio import to_thread

from app.core.config import settings
from app.services.intake.storage import (
    get_object_storage,
)
from app.services.ocr.factory import (
    get_ocr_provider,
)
from app.services.processing.preprocessing import (
    image_to_png_bytes,
    preprocess_page,
    render_document_pages,
)
from app.services.processing.repository import (
    complete_ocr_run,
    complete_processing_run,
    create_document_page,
    create_ocr_run,
    fail_processing_run,
    save_ocr_page_result,
    set_document_status,
    start_processing_run,
)


class DocumentProcessingError(RuntimeError):
    """Controlled processing-pipeline failure."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        processing_run_id: str | None = None,
    ) -> None:
        super().__init__(message)

        self.code = code
        self.processing_run_id = processing_run_id


async def process_document_pipeline(
    document_id: str,
) -> dict[str, Any]:
    run: dict[str, Any] | None = None

    try:
        run = await start_processing_run(
            document_id
        )

        processing_run_id = str(
            run["processing_run_id"]
        )

        storage = get_object_storage()

        source_content = await to_thread.run_sync(
            lambda: storage.get_object_bytes(
                bucket=run["storage_bucket"],
                object_key=run["storage_object_key"],
            )
        )

        rendered_pages = await to_thread.run_sync(
            lambda: render_document_pages(
                content=source_content,
                media_type=run["detected_media_type"],
                pdf_render_dpi=settings.pdf_render_dpi,
            )
        )

        prepared_pages: list[
            tuple[dict[str, Any], object]
        ] = []

        for rendered_page in rendered_pages:
            preprocessed = await to_thread.run_sync(
                preprocess_page,
                rendered_page.image,
            )

            original_bytes = await to_thread.run_sync(
                image_to_png_bytes,
                rendered_page.image,
            )

            processed_bytes = await to_thread.run_sync(
                image_to_png_bytes,
                preprocessed.image,
            )

            page_prefix = (
                f"documents/{document_id}/"
                f"runs/{processing_run_id}/"
                f"page-{rendered_page.page_number:04d}"
            )

            original_key = (
                f"{page_prefix}/original.png"
            )

            processed_key = (
                f"{page_prefix}/processed.png"
            )

            artifact_metadata = {
                "document-id": document_id,
                "processing-run-id": processing_run_id,
                "page-number": str(
                    rendered_page.page_number
                ),
            }

            await to_thread.run_sync(
                lambda: storage.put_page_artifact(
                    object_key=original_key,
                    content=original_bytes,
                    metadata={
                        **artifact_metadata,
                        "artifact-type": "original-page",
                    },
                )
            )

            await to_thread.run_sync(
                lambda: storage.put_page_artifact(
                    object_key=processed_key,
                    content=processed_bytes,
                    metadata={
                        **artifact_metadata,
                        "artifact-type": "processed-page",
                    },
                )
            )

            page_record = await create_document_page(
                processing_run_id=processing_run_id,
                document_id=document_id,
                page_number=rendered_page.page_number,
                original_storage_bucket=(
                    settings.s3_bucket_derived_pages
                ),
                original_storage_object_key=original_key,
                processed_storage_bucket=(
                    settings.s3_bucket_derived_pages
                ),
                processed_storage_object_key=processed_key,
                width_px=preprocessed.image.width,
                height_px=preprocessed.image.height,
                preprocessing_operations=list(
                    preprocessed.operations
                ),
            )

            prepared_pages.append(
                (
                    page_record,
                    preprocessed.image,
                )
            )

        await set_document_status(
            document_id=document_id,
            status="OCR_IN_PROGRESS",
            event_type="DOCUMENT_OCR_STARTED",
            reason=(
                "The configured OCR provider started "
                "processing normalized pages."
            ),
            payload={
                "processing_run_id": processing_run_id,
                "page_count": len(prepared_pages),
                "provider": settings.ocr_provider,
            },
        )

        provider = get_ocr_provider()

        ocr_run_id = await create_ocr_run(
            processing_run_id=processing_run_id,
            document_id=document_id,
            provider=provider.name,
            provider_version=provider.version,
            language=settings.ocr_language,
        )

        page_confidences: list[float] = []
        total_token_count = 0

        for page_record, processed_image in prepared_pages:
            result = await to_thread.run_sync(
                provider.extract_page,
                processed_image,
            )

            tokens = [
                asdict(token)
                for token in result.tokens
            ]

            total_token_count += len(tokens)

            if result.average_confidence is not None:
                page_confidences.append(
                    result.average_confidence
                )

            await save_ocr_page_result(
                ocr_run_id=ocr_run_id,
                document_page_id=str(
                    page_record["id"]
                ),
                page_number=int(
                    page_record["page_number"]
                ),
                raw_text=result.text,
                average_confidence=(
                    result.average_confidence
                ),
                tokens=tokens,
            )

        await complete_ocr_run(
            ocr_run_id
        )

        await complete_processing_run(
            processing_run_id=processing_run_id,
            document_id=document_id,
        )

        document_confidence = None

        if page_confidences:
            document_confidence = round(
                mean(page_confidences),
                4,
            )

        await set_document_status(
            document_id=document_id,
            status="REVIEW_REQUIRED",
            event_type="DOCUMENT_OCR_COMPLETED",
            reason=(
                "Local OCR completed successfully. "
                "Structured field extraction and "
                "deterministic validation will run "
                "in the next pipeline milestone."
            ),
            payload={
                "processing_run_id": processing_run_id,
                "ocr_run_id": ocr_run_id,
                "page_count": len(prepared_pages),
                "token_count": total_token_count,
                "document_ocr_confidence": (
                    document_confidence
                ),
            },
        )

        return {
            "status": "completed",
            "document_id": document_id,
            "processing_run_id": processing_run_id,
            "ocr_run_id": ocr_run_id,
            "page_count": len(prepared_pages),
            "token_count": total_token_count,
            "document_ocr_confidence": (
                document_confidence
            ),
            "document_status": "REVIEW_REQUIRED",
        }

    except Exception as exc:
        processing_run_id = None

        if run is not None:
            processing_run_id = str(
                run["processing_run_id"]
            )

            try:
                await fail_processing_run(
                    processing_run_id=processing_run_id,
                    error_code=type(exc).__name__,
                    error_message=str(exc)[:2000],
                )
            except Exception:
                pass

        if isinstance(
            exc,
            DocumentProcessingError,
        ):
            raise

        raise DocumentProcessingError(
            code="DOCUMENT_PROCESSING_FAILED",
            message=str(exc),
            processing_run_id=processing_run_id,
        ) from exc