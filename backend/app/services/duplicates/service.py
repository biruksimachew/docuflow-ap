from __future__ import annotations

from typing import Any

from app.services.duplicates.matcher import (
    detect_business_duplicates,
)
from app.services.duplicates.repository import (
    complete_duplicate_check,
    fail_duplicate_check,
    load_business_identity,
    load_candidate_identities,
    start_duplicate_check,
)


async def detect_and_persist_business_duplicates(
    *,
    document_id: str,
    processing_run_id: str,
    invoice_extraction_id: str,
) -> dict[str, Any]:
    """Execute and persist deterministic business duplicate detection."""

    duplicate_check_id = await start_duplicate_check(
        document_id=document_id,
        processing_run_id=processing_run_id,
        invoice_extraction_id=(
            invoice_extraction_id
        ),
    )

    try:
        current = await load_business_identity(
            document_id=document_id,
            invoice_extraction_id=(
                invoice_extraction_id
            ),
        )

        candidates = await load_candidate_identities(
            current_document_id=document_id,
            invoice_number=(
                current.invoice_number
            ),
        )

        result = detect_business_duplicates(
            current=current,
            candidates=candidates,
        )

        await complete_duplicate_check(
            duplicate_check_id=duplicate_check_id,
            document_id=document_id,
            result=result,
        )

        return {
            "duplicate_check_id": (
                duplicate_check_id
            ),
            "ruleset_version": (
                "business-duplicate-v1"
            ),
            "outcome": result.outcome,
            "blocking": result.blocking,
            "candidate_count": (
                result.candidate_count
            ),
            "exact_match_count": (
                result.exact_match_count
            ),
            "potential_match_count": (
                result.potential_match_count
            ),
            "matched_document_id": (
                result.matched_document_id
            ),
            "matched_invoice_extraction_id": (
                result
                .matched_invoice_extraction_id
            ),
        }

    except Exception as exc:
        await fail_duplicate_check(
            duplicate_check_id=duplicate_check_id,
            error_code=type(exc).__name__,
            error_message=str(exc)[:2000],
        )

        raise