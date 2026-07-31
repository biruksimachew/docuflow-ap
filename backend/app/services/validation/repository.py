from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from app.db.database import engine
from app.services.validation.models import (
    InvoiceValidationContext,
    ValidationSummary,
)


async def load_validation_context(
    *,
    document_id: str,
    invoice_extraction_id: str,
) -> InvoiceValidationContext:
    query = text(
        """
        select
            header.vendor_name,
            header.invoice_number,
            header.invoice_date,
            header.due_date,
            header.purchase_order_number,
            header.currency,
            header.subtotal,
            header.discount_amount,
            header.shipping_amount,
            header.tax_amount,
            header.total_amount,
            invoice_number_field.raw_value
                as raw_invoice_number
        from public.invoice_headers header
        left join public.extracted_fields
            invoice_number_field
            on invoice_number_field.invoice_extraction_id =
                header.invoice_extraction_id
            and invoice_number_field.field_name =
                'invoice_number'
        where
            header.document_id =
                cast(:document_id as uuid)
            and header.invoice_extraction_id =
                cast(:invoice_extraction_id as uuid)
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
            },
        )

        row = result.mappings().one_or_none()

    if row is None:
        raise RuntimeError(
            "Canonical invoice header was not found "
            "for deterministic validation."
        )

    return InvoiceValidationContext(
        document_id=document_id,
        invoice_extraction_id=invoice_extraction_id,
        vendor_name=row["vendor_name"],
        invoice_number=row["invoice_number"],
        raw_invoice_number=row[
            "raw_invoice_number"
        ],
        invoice_date=row["invoice_date"],
        due_date=row["due_date"],
        purchase_order_number=row[
            "purchase_order_number"
        ],
        currency=row["currency"],
        subtotal=_to_decimal(
            row["subtotal"]
        ),
        discount_amount=_to_decimal(
            row["discount_amount"]
        ),
        shipping_amount=_to_decimal(
            row["shipping_amount"]
        ),
        tax_amount=_to_decimal(
            row["tax_amount"]
        ),
        total_amount=_to_decimal(
            row["total_amount"]
        ),
    )


async def start_validation_run(
    *,
    document_id: str,
    processing_run_id: str,
    invoice_extraction_id: str,
) -> str:
    validation_run_id = str(
        uuid4()
    )

    query = text(
        """
        insert into public.validation_runs (
            id,
            document_id,
            processing_run_id,
            invoice_extraction_id,
            ruleset_version,
            status
        )
        values (
            cast(:validation_run_id as uuid),
            cast(:document_id as uuid),
            cast(:processing_run_id as uuid),
            cast(:invoice_extraction_id as uuid),
            'header-rules-v1',
            'STARTED'
        )
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            query,
            {
                "validation_run_id": (
                    validation_run_id
                ),
                "document_id": document_id,
                "processing_run_id": (
                    processing_run_id
                ),
                "invoice_extraction_id": (
                    invoice_extraction_id
                ),
            },
        )

    return validation_run_id


async def complete_validation_run(
    *,
    validation_run_id: str,
    document_id: str,
    summary: ValidationSummary,
) -> None:
    insert_result = text(
        """
        insert into public.validation_results (
            validation_run_id,
            document_id,
            rule_id,
            rule_name,
            result,
            blocking,
            expected_value,
            actual_value,
            tolerance,
            message,
            details
        )
        values (
            cast(:validation_run_id as uuid),
            cast(:document_id as uuid),
            :rule_id,
            :rule_name,
            :result,
            :blocking,
            cast(:expected_value as jsonb),
            cast(:actual_value as jsonb),
            cast(:tolerance as jsonb),
            :message,
            cast(:details as jsonb)
        )
        """
    )

    complete_run = text(
        """
        update public.validation_runs
        set
            status = 'SUCCEEDED',
            overall_outcome = :overall_outcome,
            passed_count = :passed_count,
            warning_count = :warning_count,
            failed_count = :failed_count,
            blocking_count = :blocking_count,
            blocking_rule_ids =
                cast(:blocking_rule_ids as jsonb),
            error_code = null,
            error_message = null,
            completed_at = now()
        where id =
            cast(:validation_run_id as uuid)
        """
    )

    update_document = text(
        """
        update public.documents
        set
            latest_validation_run_id =
                cast(:validation_run_id as uuid),
            validation_outcome =
                :overall_outcome,
            blocking_validation_count =
                :blocking_count
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
            'DOCUMENT_VALIDATION_COMPLETED',
            'SYSTEM',
            :reason,
            cast(:payload as jsonb)
        )
        """
    )

    async with engine.begin() as connection:
        for rule_result in summary.results:
            await connection.execute(
                insert_result,
                {
                    "validation_run_id": (
                        validation_run_id
                    ),
                    "document_id": document_id,
                    "rule_id": (
                        rule_result.rule_id
                    ),
                    "rule_name": (
                        rule_result.rule_name
                    ),
                    "result": (
                        rule_result.result
                    ),
                    "blocking": (
                        rule_result.blocking
                    ),
                    "expected_value": (
                        _json_dump(
                            rule_result.expected_value
                        )
                    ),
                    "actual_value": (
                        _json_dump(
                            rule_result.actual_value
                        )
                    ),
                    "tolerance": (
                        _json_dump(
                            rule_result.tolerance
                        )
                    ),
                    "message": (
                        rule_result.message
                    ),
                    "details": (
                        _json_dump(
                            rule_result.details
                        )
                    ),
                },
            )

        await connection.execute(
            complete_run,
            {
                "validation_run_id": (
                    validation_run_id
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
                "blocking_rule_ids": (
                    json.dumps(
                        list(
                            summary.blocking_rule_ids
                        )
                    )
                ),
            },
        )

        await connection.execute(
            update_document,
            {
                "validation_run_id": (
                    validation_run_id
                ),
                "document_id": document_id,
                "overall_outcome": (
                    summary.overall_outcome
                ),
                "blocking_count": (
                    summary.blocking_count
                ),
            },
        )

        reason = (
            "Header deterministic controls passed."
            if summary.blocking_count == 0
            else (
                "One or more blocking deterministic "
                "controls require review."
            )
        )

        await connection.execute(
            insert_audit,
            {
                "document_id": document_id,
                "reason": reason,
                "payload": json.dumps(
                    {
                        "validation_run_id": (
                            validation_run_id
                        ),
                        "ruleset_version": (
                            "header-rules-v1"
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
                        "blocking_rule_ids": list(
                            summary.blocking_rule_ids
                        ),
                    }
                ),
            },
        )


async def fail_validation_run(
    *,
    validation_run_id: str,
    error_code: str,
    error_message: str,
) -> None:
    query = text(
        """
        update public.validation_runs
        set
            status = 'FAILED',
            error_code = :error_code,
            error_message = :error_message,
            completed_at = now()
        where id =
            cast(:validation_run_id as uuid)
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            query,
            {
                "validation_run_id": (
                    validation_run_id
                ),
                "error_code": error_code,
                "error_message": error_message,
            },
        )


async def get_validation_snapshot(
    document_id: str,
) -> dict[str, Any] | None:
    document_query = text(
        """
        select
            id,
            status,
            validation_outcome,
            blocking_validation_count,
            latest_validation_run_id
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
            ruleset_version,
            status,
            overall_outcome,
            passed_count,
            warning_count,
            failed_count,
            blocking_count,
            blocking_rule_ids,
            error_code,
            error_message,
            started_at,
            completed_at
        from public.validation_runs
        where document_id =
            cast(:document_id as uuid)
        order by started_at desc
        limit 1
        """
    )

    results_query = text(
        """
        select
            id,
            rule_id,
            rule_name,
            result,
            blocking,
            expected_value,
            actual_value,
            tolerance,
            message,
            details,
            created_at
        from public.validation_results
        where validation_run_id =
            cast(:validation_run_id as uuid)
        order by rule_id
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
            document_result.mappings().one_or_none()
        )

        if document is None:
            return None

        run_result = await connection.execute(
            run_query,
            {
                "document_id": document_id,
            },
        )

        validation_run = (
            run_result.mappings().one_or_none()
        )

        if validation_run is None:
            return {
                "document": dict(document),
                "validation_run": None,
                "validation_results": [],
            }

        results_result = await connection.execute(
            results_query,
            {
                "validation_run_id": str(
                    validation_run["id"]
                ),
            },
        )

        validation_results = [
            dict(row)
            for row in (
                results_result.mappings().all()
            )
        ]

    return {
        "document": dict(document),
        "validation_run": dict(
            validation_run
        ),
        "validation_results": (
            validation_results
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


def _json_dump(
    value: Any,
) -> str:
    return json.dumps(
        _json_safe(value)
    )


def _json_safe(
    value: Any,
) -> Any:
    if isinstance(
        value,
        Decimal,
    ):
        return str(value)

    if isinstance(
        value,
        date,
    ):
        return value.isoformat()

    if isinstance(
        value,
        dict,
    ):
        return {
            key: _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):
        return [
            _json_safe(item)
            for item in value
        ]

    return value