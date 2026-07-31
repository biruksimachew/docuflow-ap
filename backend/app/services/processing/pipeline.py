from __future__ import annotations

from dataclasses import asdict
from statistics import mean
from typing import Any

from anyio import to_thread

from app.core.config import settings
from app.services.extraction.service import (
    extract_and_persist_header,
)
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
from app.services.duplicates.service import (
    detect_and_persist_business_duplicates,
)
from app.services.matching.service import (
    match_and_persist_vendor_and_po,
)
from app.services.validation.service import (
    validate_and_persist_invoice,
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
                        "artifact-type": (
                            "original-page"
                        ),
                    },
                )
            )

            await to_thread.run_sync(
                lambda: storage.put_page_artifact(
                    object_key=processed_key,
                    content=processed_bytes,
                    metadata={
                        **artifact_metadata,
                        "artifact-type": (
                            "processed-page"
                        ),
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
                original_storage_object_key=(
                    original_key
                ),
                processed_storage_bucket=(
                    settings.s3_bucket_derived_pages
                ),
                processed_storage_object_key=(
                    processed_key
                ),
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
                "processing_run_id": (
                    processing_run_id
                ),
                "page_count": len(
                    prepared_pages
                ),
                "provider": (
                    settings.ocr_provider
                ),
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

        for (
            page_record,
            processed_image,
        ) in prepared_pages:
            result = await to_thread.run_sync(
                provider.extract_page,
                processed_image,
            )

            tokens = [
                asdict(token)
                for token in result.tokens
            ]

            total_token_count += len(
                tokens
            )

            if (
                result.average_confidence
                is not None
            ):
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

        document_ocr_confidence = None

        if page_confidences:
            document_ocr_confidence = round(
                mean(page_confidences),
                4,
            )

        await set_document_status(
            document_id=document_id,
            status="EXTRACTION_IN_PROGRESS",
            event_type="DOCUMENT_EXTRACTION_STARTED",
            reason=(
                "Canonical invoice header extraction "
                "started from persisted OCR evidence."
            ),
            payload={
                "processing_run_id": (
                    processing_run_id
                ),
                "ocr_run_id": ocr_run_id,
                "schema_version": "header-v1",
            },
        )

        extraction_summary = (
            await extract_and_persist_header(
                document_id=document_id,
                processing_run_id=(
                    processing_run_id
                ),
                ocr_run_id=ocr_run_id,
            )
        )

        invoice_extraction_id = (
            extraction_summary[
                "invoice_extraction_id"
            ]
        )

        await set_document_status(
            document_id=document_id,
            status="VALIDATING",
            event_type="DOCUMENT_VALIDATION_STARTED",
            reason=(
                "Authoritative deterministic header "
                "controls started."
            ),
            payload={
                "processing_run_id": (
                    processing_run_id
                ),
                "invoice_extraction_id": (
                    invoice_extraction_id
                ),
                "ruleset_version": (
                    "invoice-rules-v2"
                ),
            },
        )

        validation_summary = (
            await validate_and_persist_invoice(
                document_id=document_id,
                processing_run_id=(
                    processing_run_id
                ),
                invoice_extraction_id=(
                    invoice_extraction_id
                ),
            )
        )

        await set_document_status(
            document_id=document_id,
            status="VALIDATING",
            event_type=(
                "DOCUMENT_DUPLICATE_CHECK_STARTED"
            ),
            reason=(
                "Deterministic business duplicate "
                "detection started."
            ),
            payload={
                "processing_run_id": (
                    processing_run_id
                ),
                "invoice_extraction_id": (
                    invoice_extraction_id
                ),
                "ruleset_version": (
                    "business-duplicate-v1"
                ),
            },
        )

        duplicate_summary = (
            await detect_and_persist_business_duplicates(
                document_id=document_id,
                processing_run_id=(
                    processing_run_id
                ),
                invoice_extraction_id=(
                    invoice_extraction_id
                ),
            )
        )

        await set_document_status(
            document_id=document_id,
            status="VALIDATING",
            event_type=(
                "DOCUMENT_MATCHING_STARTED"
            ),
            reason=(
                "Vendor identity and purchase-order "
                "matching started."
            ),
            payload={
                "processing_run_id": (
                    processing_run_id
                ),
                "invoice_extraction_id": (
                    invoice_extraction_id
                ),
                "vendor_ruleset_version": (
                    "vendor-identity-v1"
                ),
                "po_ruleset_version": (
                    "purchase-order-v1"
                ),
            },
        )

        matching_summary = (
            await match_and_persist_vendor_and_po(
                document_id=document_id,
                processing_run_id=(
                    processing_run_id
                ),
                invoice_extraction_id=(
                    invoice_extraction_id
                ),
            )
        )

        await complete_processing_run(
            processing_run_id=processing_run_id,
            document_id=document_id,
        )

        blocking_rule_ids = (
            validation_summary[
                "blocking_rule_ids"
            ]
        )

        missing_required_fields = (
            extraction_summary[
                "missing_required_fields"
            ]
        )

        duplicate_outcome = (
            duplicate_summary[
                "outcome"
            ]
        )

        duplicate_blocking = (
            duplicate_summary[
                "blocking"
            ]
        )

        vendor_outcome = (
            matching_summary[
                "vendor_outcome"
            ]
        )

        po_outcome = (
            matching_summary[
                "po_outcome"
            ]
        )

        matching_blocking = (
            matching_summary[
                "matching_blocking"
            ]
        )

        if duplicate_outcome == "BUSINESS_DUPLICATE":
            review_reason = (
                "The canonical invoice exactly matches "
                "a previously processed business invoice."
            )
        elif duplicate_outcome == "POTENTIAL_DUPLICATE":
            review_reason = (
                "The vendor and invoice number match a "
                "previous invoice, but one or more other "
                "identity fields differ."
            )
        elif blocking_rule_ids:
            review_reason = (
                "One or more authoritative "
                "deterministic controls failed or "
                "could not be proven."
            )
        elif vendor_outcome != "MATCHED":
            review_reason = (
                "The extracted supplier could not be "
                "resolved to one unambiguous active "
                "vendor-master record."
            )
        elif po_outcome != "MATCHED":
            review_reason = (
                "The extracted purchase order could not "
                "be matched completely to the invoice."
            )
        else:
            review_reason = (
                "Extraction, validation, duplicate, "
                "vendor and purchase-order controls "
                "passed. The final approval decision "
                "engine is still pending."
            )

        await set_document_status(
            document_id=document_id,
            status="REVIEW_REQUIRED",
            event_type="DOCUMENT_REVIEW_REQUIRED",
            reason=review_reason,
            payload={
                "processing_run_id": (
                    processing_run_id
                ),
                "ocr_run_id": ocr_run_id,
                "invoice_extraction_id": (
                    invoice_extraction_id
                ),
                "validation_run_id": (
                    validation_summary[
                        "validation_run_id"
                    ]
                ),
                "page_count": len(
                    prepared_pages
                ),
                "token_count": (
                    total_token_count
                ),
                "document_ocr_confidence": (
                    document_ocr_confidence
                ),
                "header_confidence": (
                    extraction_summary[
                        "header_confidence"
                    ]
                ),
                "missing_required_fields": (
                    missing_required_fields
                ),
                "validation_outcome": (
                    validation_summary[
                        "overall_outcome"
                    ]
                ),
                "blocking_rule_ids": (
                    blocking_rule_ids
                ),
                "duplicate_check_id": (
                    duplicate_summary[
                        "duplicate_check_id"
                    ]
                ),
                "duplicate_outcome": (
                    duplicate_outcome
                ),
                "duplicate_blocking": (
                    duplicate_blocking
                ),
                "matched_duplicate_document_id": (
                    duplicate_summary[
                        "matched_document_id"
                    ]
                ),
                "vendor_match_run_id": (
                    matching_summary[
                        "vendor_match_run_id"
                    ]
                ),
                "vendor_outcome": (
                    vendor_outcome
                ),
                "matched_vendor_id": (
                    matching_summary[
                        "matched_vendor_id"
                    ]
                ),
                "po_match_run_id": (
                    matching_summary[
                        "po_match_run_id"
                    ]
                ),
                "po_outcome": (
                    po_outcome
                ),
                "matched_purchase_order_id": (
                    matching_summary[
                        "matched_purchase_order_id"
                    ]
                ),
                "matching_blocking": (
                    matching_blocking
                ),
                "pending_controls": [
                    "decision_engine",
                ],
            },
        )

        return {
            "status": "completed",
            "document_id": document_id,
            "processing_run_id": (
                processing_run_id
            ),
            "ocr_run_id": ocr_run_id,
            "invoice_extraction_id": (
                invoice_extraction_id
            ),
            "validation_run_id": (
                validation_summary[
                    "validation_run_id"
                ]
            ),
            "page_count": len(
                prepared_pages
            ),
            "token_count": (
                total_token_count
            ),
            "document_ocr_confidence": (
                document_ocr_confidence
            ),
            "header_confidence": (
                extraction_summary[
                    "header_confidence"
                ]
            ),
            "extracted_field_count": (
                extraction_summary[
                    "field_count"
                ]
            ),
            "missing_required_fields": (
                missing_required_fields
            ),
            "validation_outcome": (
                validation_summary[
                    "overall_outcome"
                ]
            ),
            "blocking_rule_ids": (
                blocking_rule_ids
            ),
            "duplicate_check_id": (
                duplicate_summary[
                    "duplicate_check_id"
                ]
            ),
            "duplicate_outcome": (
                duplicate_outcome
            ),
            "duplicate_blocking": (
                duplicate_blocking
            ),
            "matched_duplicate_document_id": (
                duplicate_summary[
                    "matched_document_id"
                ]
            ),
            "vendor_match_run_id": (
                matching_summary[
                    "vendor_match_run_id"
                ]
            ),
            "vendor_outcome": (
                vendor_outcome
            ),
            "matched_vendor_id": (
                matching_summary[
                    "matched_vendor_id"
                ]
            ),
            "po_match_run_id": (
                matching_summary[
                    "po_match_run_id"
                ]
            ),
            "po_outcome": (
                po_outcome
            ),
            "matched_purchase_order_id": (
                matching_summary[
                    "matched_purchase_order_id"
                ]
            ),
            "matching_blocking": (
                matching_blocking
            ),
            "canonical_header": (
                extraction_summary[
                    "canonical_header"
                ]
            ),
            "document_status": (
                "REVIEW_REQUIRED"
            ),
        }

    except Exception as exc:
        processing_run_id = None

        if run is not None:
            processing_run_id = str(
                run["processing_run_id"]
            )

            try:
                await fail_processing_run(
                    processing_run_id=(
                        processing_run_id
                    ),
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