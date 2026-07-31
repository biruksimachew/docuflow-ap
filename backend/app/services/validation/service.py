from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.services.validation.repository import (
    complete_validation_run,
    fail_validation_run,
    load_validation_context,
    start_validation_run,
)
from app.services.validation.rules import (
    validate_invoice_header,
)


async def validate_and_persist_invoice(
    *,
    document_id: str,
    processing_run_id: str,
    invoice_extraction_id: str,
) -> dict[str, Any]:
    """Execute and persist deterministic invoice controls."""

    validation_run_id = await start_validation_run(
        document_id=document_id,
        processing_run_id=processing_run_id,
        invoice_extraction_id=(
            invoice_extraction_id
        ),
    )

    try:
        context = await load_validation_context(
            document_id=document_id,
            invoice_extraction_id=(
                invoice_extraction_id
            ),
        )

        summary = validate_invoice_header(
            context=context,
            allowed_currencies=(
                settings.allowed_currency_set
            ),
            currency_tolerance=(
                settings.validation_currency_tolerance
            ),
            future_tolerance_days=(
                settings.invoice_future_tolerance_days
            ),
        )

        await complete_validation_run(
            validation_run_id=(
                validation_run_id
            ),
            document_id=document_id,
            summary=summary,
        )

        return {
            "validation_run_id": (
                validation_run_id
            ),
            "ruleset_version": (
                "invoice-rules-v2"
            ),
            "overall_outcome": (
                summary.overall_outcome
            ),
            "passed_count": (
                summary.passed_count
            ),
            "warning_count": (
                summary.warning_count
            ),
            "failed_count": (
                summary.failed_count
            ),
            "blocking_count": (
                summary.blocking_count
            ),
            "blocking_rule_ids": list(
                summary.blocking_rule_ids
            ),
        }

    except Exception as exc:
        await fail_validation_run(
            validation_run_id=(
                validation_run_id
            ),
            error_code=type(exc).__name__,
            error_message=str(exc)[:2000],
        )

        raise