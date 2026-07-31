from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.core.config import settings
from app.services.matching.engine import (
    evaluate_purchase_order_match,
    normalize_name,
    resolve_vendor_identity,
)
from app.services.matching.repository import (
    complete_po_match_run,
    complete_vendor_match_run,
    fail_po_match_run,
    fail_vendor_match_run,
    load_invoice_match_input,
    load_purchase_order,
    load_vendor_candidates,
    start_po_match_run,
    start_vendor_match_run,
)


async def match_and_persist_vendor_and_po(
    *,
    document_id: str,
    processing_run_id: str,
    invoice_extraction_id: str,
) -> dict[str, Any]:
    """Resolve vendor identity and match the invoice to a PO."""

    invoice = await load_invoice_match_input(
        document_id=document_id,
        invoice_extraction_id=(
            invoice_extraction_id
        ),
    )

    vendor_run_id = (
        await start_vendor_match_run(
            document_id=document_id,
            processing_run_id=(
                processing_run_id
            ),
            invoice_extraction_id=(
                invoice_extraction_id
            ),
        )
    )

    try:
        normalized_vendor_name = (
            normalize_name(
                invoice.vendor_name
            )
            if invoice.vendor_name
            else ""
        )

        vendor_candidates = (
            await load_vendor_candidates(
                normalized_vendor_name
            )
            if normalized_vendor_name
            else ()
        )

        vendor_result = (
            resolve_vendor_identity(
                input_vendor_name=(
                    invoice.vendor_name
                ),
                candidates=(
                    vendor_candidates
                ),
            )
        )

        await complete_vendor_match_run(
            run_id=vendor_run_id,
            document_id=document_id,
            result=vendor_result,
        )

    except Exception as exc:
        await fail_vendor_match_run(
            run_id=vendor_run_id,
            error_code=type(exc).__name__,
            error_message=str(exc)[:2000],
        )

        raise

    po_run_id = await start_po_match_run(
        document_id=document_id,
        processing_run_id=(
            processing_run_id
        ),
        invoice_extraction_id=(
            invoice_extraction_id
        ),
        vendor_match_run_id=(
            vendor_run_id
        ),
    )

    try:
        purchase_order = (
            await load_purchase_order(
                invoice.purchase_order_number
            )
        )

        po_result = (
            evaluate_purchase_order_match(
                invoice=invoice,
                resolved_vendor_id=(
                    vendor_result
                    .matched_vendor_id
                ),
                purchase_order=(
                    purchase_order
                ),
                tolerance=Decimal(
                    str(
                        settings
                        .validation_currency_tolerance
                    )
                ),
            )
        )

        await complete_po_match_run(
            run_id=po_run_id,
            document_id=document_id,
            result=po_result,
        )

    except Exception as exc:
        await fail_po_match_run(
            run_id=po_run_id,
            error_code=type(exc).__name__,
            error_message=str(exc)[:2000],
        )

        raise

    matching_blocking = (
        vendor_result.blocking
        or po_result.blocking
    )

    return {
        "vendor_match_run_id": (
            vendor_run_id
        ),
        "vendor_ruleset_version": (
            "vendor-identity-v1"
        ),
        "vendor_outcome": (
            vendor_result.outcome
        ),
        "matched_vendor_id": (
            vendor_result
            .matched_vendor_id
        ),
        "po_match_run_id": (
            po_run_id
        ),
        "po_ruleset_version": (
            "purchase-order-v1"
        ),
        "po_outcome": (
            po_result.outcome
        ),
        "matched_purchase_order_id": (
            po_result
            .matched_purchase_order_id
        ),
        "matched_line_count": (
            po_result.matched_line_count
        ),
        "mismatched_line_count": (
            po_result
            .mismatched_line_count
        ),
        "matching_blocking": (
            matching_blocking
        ),
    }