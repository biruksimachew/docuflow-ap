from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from app.db.database import engine
from app.services.extraction.models import (
    HeaderExtractionResult,
    OCRPageInput,
)


async def load_ocr_pages(
    ocr_run_id: str,
) -> tuple[OCRPageInput, ...]:
    query = text(
        """
        select
            page_number,
            raw_text,
            average_confidence,
            tokens
        from public.ocr_page_results
        where ocr_run_id =
            cast(:ocr_run_id as uuid)
        order by page_number
        """
    )

    async with engine.connect() as connection:
        result = await connection.execute(
            query,
            {
                "ocr_run_id": ocr_run_id,
            },
        )

        rows = result.mappings().all()

    pages: list[OCRPageInput] = []

    for row in rows:
        raw_tokens = row["tokens"]

        if isinstance(raw_tokens, str):
            raw_tokens = json.loads(
                raw_tokens
            )

        pages.append(
            OCRPageInput(
                page_number=int(
                    row["page_number"]
                ),
                raw_text=str(
                    row["raw_text"] or ""
                ),
                average_confidence=(
                    float(
                        row["average_confidence"]
                    )
                    if row["average_confidence"]
                    is not None
                    else None
                ),
                tokens=tuple(
                    raw_tokens or []
                ),
            )
        )

    return tuple(pages)


async def start_invoice_extraction(
    *,
    document_id: str,
    processing_run_id: str,
    ocr_run_id: str,
) -> str:
    extraction_id = str(
        uuid4()
    )

    query = text(
        """
        insert into public.invoice_extractions (
            id,
            document_id,
            processing_run_id,
            ocr_run_id,
            schema_version,
            status
        )
        values (
            cast(:extraction_id as uuid),
            cast(:document_id as uuid),
            cast(:processing_run_id as uuid),
            cast(:ocr_run_id as uuid),
            'header-v1',
            'STARTED'
        )
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            query,
            {
                "extraction_id": extraction_id,
                "document_id": document_id,
                "processing_run_id": processing_run_id,
                "ocr_run_id": ocr_run_id,
            },
        )

    return extraction_id


def _to_date(
    value: str | None,
) -> date | None:
    """Convert a normalized ISO date into a database-ready value."""

    if value is None:
        return None

    return date.fromisoformat(value)


def _to_decimal(
    value: str | None,
) -> Decimal | None:
    """Convert a normalized monetary string into a database-ready value."""

    if value is None:
        return None

    return Decimal(value)


async def complete_invoice_extraction(
    *,
    extraction_id: str,
    document_id: str,
    result: HeaderExtractionResult,
) -> None:
    insert_field = text(
        """
        insert into public.extracted_fields (
            invoice_extraction_id,
            document_id,
            field_name,
            raw_value,
            normalized_value,
            normalized_text,
            confidence,
            confidence_source,
            extraction_method,
            page_number,
            evidence
        )
        values (
            cast(:extraction_id as uuid),
            cast(:document_id as uuid),
            :field_name,
            :raw_value,
            cast(:normalized_value as jsonb),
            :normalized_text,
            :confidence,
            :confidence_source,
            :extraction_method,
            :page_number,
            cast(:evidence as jsonb)
        )
        """
    )

    insert_header = text(
        """
        insert into public.invoice_headers (
            invoice_extraction_id,
            document_id,
            vendor_name,
            invoice_number,
            invoice_date,
            due_date,
            purchase_order_number,
            currency,
            subtotal,
            discount_amount,
            shipping_amount,
            tax_amount,
            total_amount
        )
        values (
            cast(:extraction_id as uuid),
            cast(:document_id as uuid),
            :vendor_name,
            :invoice_number,
            cast(:invoice_date as date),
            cast(:due_date as date),
            :purchase_order_number,
            :currency,
            cast(:subtotal as numeric),
            cast(:discount_amount as numeric),
            cast(:shipping_amount as numeric),
            cast(:tax_amount as numeric),
            cast(:total_amount as numeric)
        )
        """
    )

    complete_extraction = text(
        """
        update public.invoice_extractions
        set
            status = 'SUCCEEDED',
            header_confidence = :header_confidence,
            extracted_field_count = :field_count,
            missing_required_fields =
                cast(:missing_required_fields as jsonb),
            error_code = null,
            error_message = null,
            completed_at = now()
        where id = cast(:extraction_id as uuid)
        """
    )

    update_document = text(
        """
        update public.documents
        set
            header_confidence = :header_confidence,
            latest_invoice_extraction_id =
                cast(:extraction_id as uuid)
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
            'DOCUMENT_HEADER_EXTRACTED',
            'SYSTEM',
            :reason,
            cast(:payload as jsonb)
        )
        """
    )

    header = result.canonical_header

    async with engine.begin() as connection:
        for field in result.fields:
            await connection.execute(
                insert_field,
                {
                    "extraction_id": extraction_id,
                    "document_id": document_id,
                    "field_name": field.field_name,
                    "raw_value": field.raw_value,
                    "normalized_value": json.dumps(
                        field.normalized_value
                    ),
                    "normalized_text": (
                        field.normalized_value
                    ),
                    "confidence": field.confidence,
                    "confidence_source": (
                        field.confidence_source
                    ),
                    "extraction_method": (
                        field.extraction_method
                    ),
                    "page_number": field.page_number,
                    "evidence": json.dumps(
                        field.evidence
                    ),
                },
            )

        await connection.execute(
            insert_header,
            {
                "extraction_id": extraction_id,
                "document_id": document_id,
                "vendor_name": header[
                    "vendor_name"
                ],
                "invoice_number": header[
                    "invoice_number"
                ],
                "invoice_date": _to_date(
                    header["invoice_date"]
                ),
                "due_date": _to_date(
                    header["due_date"]
                ),
                "purchase_order_number": header[
                    "purchase_order_number"
                ],
                "currency": header[
                    "currency"
                ],
                "subtotal": _to_decimal(
                    header["subtotal"]
                ),
                "discount_amount": _to_decimal(
                    header["discount_amount"]
                ),
                "shipping_amount": _to_decimal(
                    header["shipping_amount"]
                ),
                "tax_amount": _to_decimal(
                    header["tax_amount"]
                ),
                "total_amount": _to_decimal(
                    header["total_amount"]
                ),
            },
        )

        await connection.execute(
            complete_extraction,
            {
                "extraction_id": extraction_id,
                "header_confidence": (
                    result.header_confidence
                ),
                "field_count": len(
                    result.fields
                ),
                "missing_required_fields": (
                    json.dumps(
                        list(
                            result.missing_required_fields
                        )
                    )
                ),
            },
        )

        await connection.execute(
            update_document,
            {
                "document_id": document_id,
                "extraction_id": extraction_id,
                "header_confidence": (
                    result.header_confidence
                ),
            },
        )

        missing_fields = list(
            result.missing_required_fields
        )

        reason = (
            "Canonical header extraction completed."
            if not missing_fields
            else (
                "Canonical header extraction completed "
                "with missing required fields."
            )
        )

        await connection.execute(
            insert_audit,
            {
                "document_id": document_id,
                "reason": reason,
                "payload": json.dumps(
                    {
                        "invoice_extraction_id": (
                            extraction_id
                        ),
                        "schema_version": "header-v1",
                        "header_confidence": (
                            result.header_confidence
                        ),
                        "extracted_field_count": len(
                            result.fields
                        ),
                        "missing_required_fields": (
                            missing_fields
                        ),
                    }
                ),
            },
        )


async def fail_invoice_extraction(
    *,
    extraction_id: str,
    error_code: str,
    error_message: str,
) -> None:
    query = text(
        """
        update public.invoice_extractions
        set
            status = 'FAILED',
            error_code = :error_code,
            error_message = :error_message,
            completed_at = now()
        where id = cast(:extraction_id as uuid)
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            query,
            {
                "extraction_id": extraction_id,
                "error_code": error_code,
                "error_message": error_message,
            },
        )


async def get_extraction_snapshot(
    document_id: str,
) -> dict[str, Any] | None:
    extraction_query = text(
        """
        select
            extraction.id,
            extraction.document_id,
            extraction.processing_run_id,
            extraction.ocr_run_id,
            extraction.schema_version,
            extraction.status,
            extraction.header_confidence,
            extraction.extracted_field_count,
            extraction.missing_required_fields,
            extraction.error_code,
            extraction.error_message,
            extraction.started_at,
            extraction.completed_at
        from public.invoice_extractions extraction
        where extraction.document_id =
            cast(:document_id as uuid)
        order by extraction.started_at desc
        limit 1
        """
    )

    fields_query = text(
        """
        select
            id,
            field_name,
            raw_value,
            normalized_value,
            normalized_text,
            confidence,
            confidence_source,
            extraction_method,
            page_number,
            evidence,
            created_at
        from public.extracted_fields
        where invoice_extraction_id =
            cast(:extraction_id as uuid)
        order by field_name
        """
    )

    header_query = text(
        """
        select
            id,
            vendor_name,
            invoice_number,
            invoice_date,
            due_date,
            purchase_order_number,
            currency,
            subtotal,
            discount_amount,
            shipping_amount,
            tax_amount,
            total_amount,
            created_at,
            updated_at
        from public.invoice_headers
        where invoice_extraction_id =
            cast(:extraction_id as uuid)
        limit 1
        """
    )

    document_query = text(
        """
        select
            id,
            status,
            header_confidence,
            latest_invoice_extraction_id
        from public.documents
        where id = cast(:document_id as uuid)
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

        extraction_result = await connection.execute(
            extraction_query,
            {
                "document_id": document_id,
            },
        )

        extraction = (
            extraction_result.mappings().one_or_none()
        )

        if extraction is None:
            return {
                "document": dict(document),
                "invoice_extraction": None,
                "canonical_header": None,
                "extracted_fields": [],
            }

        extraction_id = str(
            extraction["id"]
        )

        fields_result = await connection.execute(
            fields_query,
            {
                "extraction_id": extraction_id,
            },
        )

        fields: list[dict[str, Any]] = []

        for row in fields_result.mappings().all():
            field = dict(row)

            if field["confidence"] is not None:
                field["confidence"] = float(
                    field["confidence"]
                )

            fields.append(field)

        header_result = await connection.execute(
            header_query,
            {
                "extraction_id": extraction_id,
            },
        )

        header = (
            header_result.mappings().one_or_none()
        )

    document_payload = dict(document)

    if document_payload["header_confidence"] is not None:
        document_payload["header_confidence"] = float(
            document_payload["header_confidence"]
        )

    extraction_payload = dict(extraction)

    if extraction_payload["header_confidence"] is not None:
        extraction_payload["header_confidence"] = float(
            extraction_payload["header_confidence"]
        )

    header_payload = (
        dict(header)
        if header is not None
        else None
    )

    return {
        "document": document_payload,
        "invoice_extraction": extraction_payload,
        "canonical_header": header_payload,
        "extracted_fields": fields,
    }