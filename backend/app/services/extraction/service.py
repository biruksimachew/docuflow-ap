from __future__ import annotations

from typing import Any

from app.services.extraction.header import (
    extract_header_fields,
)
from app.services.extraction.repository import (
    complete_invoice_extraction,
    fail_invoice_extraction,
    load_ocr_pages,
    start_invoice_extraction,
)


async def extract_and_persist_header(
    *,
    document_id: str,
    processing_run_id: str,
    ocr_run_id: str,
) -> dict[str, Any]:
    """Extract and persist the canonical invoice header."""

    extraction_id = await start_invoice_extraction(
        document_id=document_id,
        processing_run_id=processing_run_id,
        ocr_run_id=ocr_run_id,
    )

    try:
        pages = await load_ocr_pages(
            ocr_run_id
        )

        if not pages:
            raise RuntimeError(
                "No OCR page results were available "
                "for header extraction."
            )

        result = extract_header_fields(
            pages
        )

        await complete_invoice_extraction(
            extraction_id=extraction_id,
            document_id=document_id,
            result=result,
        )

        return {
            "invoice_extraction_id": extraction_id,
            "schema_version": "header-v1",
            "header_confidence": (
                result.header_confidence
            ),
            "field_count": len(
                result.fields
            ),
            "missing_required_fields": list(
                result.missing_required_fields
            ),
            "canonical_header": (
                result.canonical_header
            ),
        }

    except Exception as exc:
        await fail_invoice_extraction(
            extraction_id=extraction_id,
            error_code=type(exc).__name__,
            error_message=str(exc)[:2000],
        )

        raise