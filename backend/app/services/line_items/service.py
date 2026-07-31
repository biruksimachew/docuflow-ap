from __future__ import annotations

from typing import Any

from app.services.extraction.models import OCRPageInput
from app.services.line_items.extractor import (
    extract_line_items,
)
from app.services.line_items.repository import (
    persist_line_items,
)


async def extract_and_persist_line_items(
    *,
    document_id: str,
    invoice_extraction_id: str,
    pages: tuple[OCRPageInput, ...],
    header_currency: str | None,
) -> dict[str, Any]:
    """Extract and persist canonical invoice line items."""

    result = extract_line_items(
        pages=pages,
        header_currency=header_currency,
    )

    await persist_line_items(
        invoice_extraction_id=(
            invoice_extraction_id
        ),
        document_id=document_id,
        result=result,
    )

    return {
        "line_item_count": (
            result.item_count
        ),
        "line_item_confidence": (
            result.average_confidence
        ),
        "extraction_method": (
            "tabular_numeric_tail_v1"
        ),
    }