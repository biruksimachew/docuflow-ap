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
from app.services.line_items.service import (
    extract_and_persist_line_items,
)


async def extract_and_persist_header(
    *,
    document_id: str,
    processing_run_id: str,
    ocr_run_id: str,
) -> dict[str, Any]:
    """
    Extract and persist the canonical invoice header and line items.

    The historical function name remains stable for existing callers.
    """

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
                "for canonical extraction."
            )

        header_result = (
            extract_header_fields(
                pages
            )
        )

        await complete_invoice_extraction(
            extraction_id=extraction_id,
            document_id=document_id,
            result=header_result,
        )

        line_item_summary = (
            await extract_and_persist_line_items(
                document_id=document_id,
                invoice_extraction_id=(
                    extraction_id
                ),
                pages=pages,
                header_currency=(
                    header_result
                    .canonical_header[
                        "currency"
                    ]
                ),
            )
        )

        return {
            "invoice_extraction_id": (
                extraction_id
            ),
            "schema_version": "header-v1",
            "header_confidence": (
                header_result
                .header_confidence
            ),
            "field_count": len(
                header_result.fields
            ),
            "missing_required_fields": list(
                header_result
                .missing_required_fields
            ),
            "canonical_header": (
                header_result
                .canonical_header
            ),
            "line_item_count": (
                line_item_summary[
                    "line_item_count"
                ]
            ),
            "line_item_confidence": (
                line_item_summary[
                    "line_item_confidence"
                ]
            ),
        }

    except Exception as exc:
        await fail_invoice_extraction(
            extraction_id=extraction_id,
            error_code=type(exc).__name__,
            error_message=str(exc)[:2000],
        )

        raise