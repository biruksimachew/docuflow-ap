from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from app.db.database import engine
from app.services.decisions.models import (
    InvoiceDecisionInput,
    InvoiceDecisionResult,
)


async def load_decision_input(
    *,
    document_id: str,
    invoice_extraction_id: str,
    validation_run_id: str,
    duplicate_check_id: str,
    vendor_match_run_id: str,
    po_match_run_id: str,
) -> InvoiceDecisionInput:
    query = text(
        """
        select
            extraction.status
                as extraction_status,
            extraction.header_confidence,
            extraction.line_item_confidence,
            extraction.line_item_count,

            validation.status
                as validation_status,
            validation.overall_outcome
                as validation_outcome,
            validation.blocking_count
                as validation_blocking_count,

            duplicate_check.status
                as duplicate_status,
            duplicate_check.outcome
                as duplicate_outcome,
            duplicate_check.blocking
                as duplicate_blocking,

            vendor_match.status
                as vendor_match_status,
            vendor_match.outcome
                as vendor_outcome,
            vendor_match.blocking
                as vendor_blocking,

            po_match.status
                as po_match_status,
            po_match.outcome
                as po_outcome,
            po_match.blocking
                as po_blocking

        from public.invoice_extractions extraction

        join public.validation_runs validation
            on validation.id =
                cast(:validation_run_id as uuid)

        join public.duplicate_checks duplicate_check
            on duplicate_check.id =
                cast(:duplicate_check_id as uuid)

        join public.vendor_match_runs vendor_match
            on vendor_match.id =
                cast(:vendor_match_run_id as uuid)

        join public.po_match_runs po_match
            on po_match.id =
                cast(:po_match_run_id as uuid)

        where
            extraction.id =
                cast(:invoice_extraction_id as uuid)
            and extraction.document_id =
                cast(:document_id as uuid)
            and validation.document_id =
                cast(:document_id as uuid)
            and duplicate_check.document_id =
                cast(:document_id as uuid)
            and vendor_match.document_id =
                cast(:document_id as uuid)
            and po_match.document_id =
                cast(:document_id as uuid)

        limit 1
        """
    )

    async with engine.connect() as connection:
        result = await connection.execute(
            query,
            {
                "document_id": document_id,
                "invoice_extraction_id": (
                    invoice_extraction_id
                ),
                "validation_run_id": (
                    validation_run_id
                ),
                "duplicate_check_id": (
                    duplicate_check_id
                ),
                "vendor_match_run_id": (
                    vendor_match_run_id
                ),
                "po_match_run_id": (
                    po_match_run_id
                ),
            },
        )

        row = result.mappings().one_or_none()

    if row is None:
        raise RuntimeError(
            "Completed control evidence could not be "
            "loaded for the invoice decision."
        )

    return InvoiceDecisionInput(
        document_id=document_id,
        invoice_extraction_id=(
            invoice_extraction_id
        ),
        extraction_status=str(
            row["extraction_status"]
        ),
        header_confidence=_to_decimal(
            row["header_confidence"]
        ),
        line_item_confidence=_to_decimal(
            row["line_item_confidence"]
        ),
        line_item_count=int(
            row["line_item_count"]
        ),
        validation_status=str(
            row["validation_status"]
        ),
        validation_outcome=(
            str(row["validation_outcome"])
            if row["validation_outcome"]
            is not None
            else None
        ),
        validation_blocking_count=int(
            row["validation_blocking_count"]
        ),
        duplicate_status=str(
            row["duplicate_status"]
        ),
        duplicate_outcome=(
            str(row["duplicate_outcome"])
            if row["duplicate_outcome"]
            is not None
            else None
        ),
        duplicate_blocking=bool(
            row["duplicate_blocking"]
        ),
        vendor_match_status=str(
            row["vendor_match_status"]
        ),
        vendor_outcome=(
            str(row["vendor_outcome"])
            if row["vendor_outcome"]
            is not None
            else None
        ),
        vendor_blocking=bool(
            row["vendor_blocking"]
        ),
        po_match_status=str(
            row["po_match_status"]
        ),
        po_outcome=(
            str(row["po_outcome"])
            if row["po_outcome"]
            is not None
            else None
        ),
        po_blocking=bool(
            row["po_blocking"]
        ),
    )


async def start_decision_run(
    *,
    document_id: str,
    processing_run_id: str,
    invoice_extraction_id: str,
    validation_run_id: str,
    duplicate_check_id: str,
    vendor_match_run_id: str,
    po_match_run_id: str,
) -> str:
    decision_run_id = str(
        uuid4()
    )

    query = text(
        """
        insert into public.decision_runs (
            id,
            document_id,
            processing_run_id,
            invoice_extraction_id,
            validation_run_id,
            duplicate_check_id,
            vendor_match_run_id,
            po_match_run_id,
            policy_version,
            status
        )
        values (
            cast(:decision_run_id as uuid),
            cast(:document_id as uuid),
            cast(:processing_run_id as uuid),
            cast(:invoice_extraction_id as uuid),
            cast(:validation_run_id as uuid),
            cast(:duplicate_check_id as uuid),
            cast(:vendor_match_run_id as uuid),
            cast(:po_match_run_id as uuid),
            'invoice-decision-v1',
            'STARTED'
        )
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            query,
            {
                "decision_run_id": (
                    decision_run_id
                ),
                "document_id": document_id,
                "processing_run_id": (
                    processing_run_id
                ),
                "invoice_extraction_id": (
                    invoice_extraction_id
                ),
                "validation_run_id": (
                    validation_run_id
                ),
                "duplicate_check_id": (
                    duplicate_check_id
                ),
                "vendor_match_run_id": (
                    vendor_match_run_id
                ),
                "po_match_run_id": (
                    po_match_run_id
                ),
            },
        )

    return decision_run_id


async def complete_decision_run(
    *,
    decision_run_id: str,
    document_id: str,
    result: InvoiceDecisionResult,
) -> None:
    complete_run = text(
        """
        update public.decision_runs
        set
            status = 'SUCCEEDED',
            outcome = :outcome,
            blocking = :blocking,
            reason_codes =
                cast(:reason_codes as jsonb),
            explanation = :explanation,
            input_snapshot =
                cast(:input_snapshot as jsonb),
            threshold_snapshot =
                cast(:threshold_snapshot as jsonb),
            error_code = null,
            error_message = null,
            completed_at = now()
        where id =
            cast(:decision_run_id as uuid)
        """
    )

    update_document = text(
        """
        update public.documents
        set
            latest_decision_run_id =
                cast(:decision_run_id as uuid),
            decision_outcome = :outcome,
            decision_reason_codes =
                cast(:reason_codes as jsonb),
            decision_explanation =
                :explanation,
            decided_at = now()
        where id = cast(:document_id as uuid)
        """
    )

    insert_audit = text(
        """
        insert into public.audit_events (
            document_id,
            event_type,
            actor_type,
            reason,
            payload
        )
        values (
            cast(:document_id as uuid),
            'DOCUMENT_DECISION_COMPLETED',
            'SYSTEM',
            :reason,
            cast(:payload as jsonb)
        )
        """
    )

    parameters = {
        "decision_run_id": (
            decision_run_id
        ),
        "document_id": document_id,
        "outcome": result.outcome,
        "blocking": result.blocking,
        "reason_codes": json.dumps(
            list(
                result.reason_codes
            )
        ),
        "explanation": (
            result.explanation
        ),
        "input_snapshot": json.dumps(
            result.input_snapshot
        ),
        "threshold_snapshot": json.dumps(
            result.threshold_snapshot
        ),
    }

    async with engine.begin() as connection:
        await connection.execute(
            complete_run,
            parameters,
        )

        await connection.execute(
            update_document,
            parameters,
        )

        await connection.execute(
            insert_audit,
            {
                "document_id": document_id,
                "reason": result.explanation,
                "payload": json.dumps(
                    {
                        "decision_run_id": (
                            decision_run_id
                        ),
                        "policy_version": (
                            "invoice-decision-v1"
                        ),
                        "outcome": (
                            result.outcome
                        ),
                        "blocking": (
                            result.blocking
                        ),
                        "reason_codes": list(
                            result.reason_codes
                        ),
                        "thresholds": (
                            result.threshold_snapshot
                        ),
                    }
                ),
            },
        )


async def fail_decision_run(
    *,
    decision_run_id: str,
    error_code: str,
    error_message: str,
) -> None:
    query = text(
        """
        update public.decision_runs
        set
            status = 'FAILED',
            error_code = :error_code,
            error_message = :error_message,
            completed_at = now()
        where id =
            cast(:decision_run_id as uuid)
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            query,
            {
                "decision_run_id": (
                    decision_run_id
                ),
                "error_code": error_code,
                "error_message": (
                    error_message
                ),
            },
        )


async def get_decision_snapshot(
    document_id: str,
) -> dict[str, Any] | None:
    document_query = text(
        """
        select
            id,
            status,
            decision_outcome,
            decision_reason_codes,
            decision_explanation,
            decided_at,
            latest_decision_run_id
        from public.documents
        where id = cast(:document_id as uuid)
        """
    )

    run_query = text(
        """
        select
            id,
            document_id,
            processing_run_id,
            invoice_extraction_id,
            validation_run_id,
            duplicate_check_id,
            vendor_match_run_id,
            po_match_run_id,
            policy_version,
            status,
            outcome,
            blocking,
            reason_codes,
            explanation,
            input_snapshot,
            threshold_snapshot,
            error_code,
            error_message,
            started_at,
            completed_at
        from public.decision_runs
        where document_id =
            cast(:document_id as uuid)
        order by started_at desc
        limit 1
        """
    )

    async with engine.connect() as connection:
        document_result = await connection.execute(
            document_query,
            {
                "document_id": document_id,
            },
        )

        document = (
            document_result
            .mappings()
            .one_or_none()
        )

        if document is None:
            return None

        run_result = await connection.execute(
            run_query,
            {
                "document_id": document_id,
            },
        )

        decision_run = (
            run_result
            .mappings()
            .one_or_none()
        )

    return {
        "document": dict(
            document
        ),
        "decision_run": (
            dict(decision_run)
            if decision_run is not None
            else None
        ),
    }


def _to_decimal(
    value: Any,
) -> Decimal | None:
    if value is None:
        return None

    if isinstance(
        value,
        Decimal,
    ):
        return value

    return Decimal(
        str(value)
    )