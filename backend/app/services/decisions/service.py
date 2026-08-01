from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.decisions.engine import (
    decide_invoice,
)
from app.services.decisions.repository import (
    complete_decision_run,
    fail_decision_run,
    load_decision_input,
    start_decision_run,
)
from app.services.reviews.service import (
    ensure_review_case_for_decision,
)


async def decide_and_persist_invoice(
    *,
    document_id: str,
    processing_run_id: str,
    invoice_extraction_id: str,
    validation_run_id: str,
    duplicate_check_id: str,
    vendor_match_run_id: str,
    po_match_run_id: str,
) -> dict[str, Any]:
    """Execute and persist the authoritative invoice decision."""

    decision_run_id = await start_decision_run(
        document_id=document_id,
        processing_run_id=processing_run_id,
        invoice_extraction_id=(
            invoice_extraction_id
        ),
        validation_run_id=validation_run_id,
        duplicate_check_id=duplicate_check_id,
        vendor_match_run_id=(
            vendor_match_run_id
        ),
        po_match_run_id=po_match_run_id,
    )

    decision_completed = False

    try:
        decision_input = await load_decision_input(
            document_id=document_id,
            invoice_extraction_id=(
                invoice_extraction_id
            ),
            validation_run_id=(
                validation_run_id
            ),
            duplicate_check_id=(
                duplicate_check_id
            ),
            vendor_match_run_id=(
                vendor_match_run_id
            ),
            po_match_run_id=(
                po_match_run_id
            ),
        )

        result = decide_invoice(
            decision_input=decision_input,
            header_confidence_min=(
                _threshold(
                    "DECISION_HEADER_CONFIDENCE_MIN",
                    "0.90",
                )
            ),
            line_item_confidence_min=(
                _threshold(
                    "DECISION_LINE_ITEM_CONFIDENCE_MIN",
                    "0.85",
                )
            ),
        )

        await complete_decision_run(
            decision_run_id=decision_run_id,
            document_id=document_id,
            result=result,
        )

        decision_completed = True

        review_case = None

        if result.outcome == "REVIEW_REQUIRED":
            review_case = (
                await ensure_review_case_for_decision(
                    document_id=document_id,
                    decision_run_id=decision_run_id,
                    reason_codes=list(
                        result.reason_codes
                    ),
                    explanation=result.explanation,
                )
            )

        return {
            "decision_run_id": decision_run_id,
            "policy_version": (
                "invoice-decision-v1"
            ),
            "outcome": result.outcome,
            "blocking": result.blocking,
            "reason_codes": list(
                result.reason_codes
            ),
            "explanation": result.explanation,
            "input_snapshot": (
                result.input_snapshot
            ),
            "threshold_snapshot": (
                result.threshold_snapshot
            ),
            "review_case_id": (
                str(review_case["id"])
                if review_case is not None
                else None
            ),
            "review_case_status": (
                str(review_case["status"])
                if review_case is not None
                else None
            ),
        }

    except Exception as exc:
        if not decision_completed:
            await fail_decision_run(
                decision_run_id=decision_run_id,
                error_code=type(exc).__name__,
                error_message=str(exc)[:2000],
            )

        raise


def _threshold(
    name: str,
    default: str,
) -> Decimal:
    raw_value = os.getenv(
        name,
        default,
    )

    try:
        return Decimal(
            raw_value
        )
    except InvalidOperation as exc:
        raise RuntimeError(
            f"{name} must be a decimal between 0 and 1."
        ) from exc