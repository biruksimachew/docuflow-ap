from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from app.db.database import engine
from app.services.line_items.models import (
    LineItemExtractionResult,
)


async def persist_line_items(
    *,
    invoice_extraction_id: str,
    document_id: str,
    result: LineItemExtractionResult,
) -> None:
    insert_item = text(
        """
        insert into public.invoice_line_items (
            invoice_extraction_id,
            document_id,
            line_number,
            description,
            supplier_sku,
            quantity,
            unit_of_measure,
            unit_price,
            tax_rate,
            line_total,
            currency,
            confidence,
            confidence_source,
            extraction_method,
            page_number,
            raw_row_text,
            normalized_values,
            field_evidence,
            row_evidence
        )
        values (
            cast(:invoice_extraction_id as uuid),
            cast(:document_id as uuid),
            :line_number,
            :description,
            :supplier_sku,
            :quantity,
            :unit_of_measure,
            :unit_price,
            :tax_rate,
            :line_total,
            :currency,
            :confidence,
            :confidence_source,
            :extraction_method,
            :page_number,
            :raw_row_text,
            cast(:normalized_values as jsonb),
            cast(:field_evidence as jsonb),
            cast(:row_evidence as jsonb)
        )
        """
    )

    update_extraction = text(
        """
        update public.invoice_extractions
        set
            line_item_count = :line_item_count,
            line_item_confidence =
                :line_item_confidence
        where id =
            cast(:invoice_extraction_id as uuid)
        """
    )

    update_document = text(
        """
        update public.documents
        set
            line_item_count = :line_item_count,
            line_item_confidence =
                :line_item_confidence
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
            'DOCUMENT_LINE_ITEMS_EXTRACTED',
            'SYSTEM',
            :reason,
            cast(:payload as jsonb)
        )
        """
    )

    confidence_value = (
        Decimal(
            str(
                result.average_confidence
            )
        )
        if result.average_confidence
        is not None
        else None
    )

    async with engine.begin() as connection:
        for item in result.items:
            await connection.execute(
                insert_item,
                {
                    "invoice_extraction_id": (
                        invoice_extraction_id
                    ),
                    "document_id": document_id,
                    "line_number": (
                        item.line_number
                    ),
                    "description": (
                        item.description
                    ),
                    "supplier_sku": (
                        item.supplier_sku
                    ),
                    "quantity": item.quantity,
                    "unit_of_measure": (
                        item.unit_of_measure
                    ),
                    "unit_price": (
                        item.unit_price
                    ),
                    "tax_rate": item.tax_rate,
                    "line_total": (
                        item.line_total
                    ),
                    "currency": item.currency,
                    "confidence": Decimal(
                        str(
                            item.confidence
                        )
                    ),
                    "confidence_source": (
                        item.confidence_source
                    ),
                    "extraction_method": (
                        item.extraction_method
                    ),
                    "page_number": (
                        item.page_number
                    ),
                    "raw_row_text": (
                        item.raw_row_text
                    ),
                    "normalized_values": (
                        json.dumps(
                            item.normalized_values
                        )
                    ),
                    "field_evidence": (
                        json.dumps(
                            item.field_evidence
                        )
                    ),
                    "row_evidence": (
                        json.dumps(
                            item.row_evidence
                        )
                    ),
                },
            )

        summary_parameters = {
            "invoice_extraction_id": (
                invoice_extraction_id
            ),
            "document_id": document_id,
            "line_item_count": (
                result.item_count
            ),
            "line_item_confidence": (
                confidence_value
            ),
        }

        await connection.execute(
            update_extraction,
            summary_parameters,
        )

        await connection.execute(
            update_document,
            summary_parameters,
        )

        reason = (
            "Canonical line-item extraction completed."
            if result.item_count > 0
            else (
                "Line-item extraction completed, "
                "but no canonical rows were detected."
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
                            invoice_extraction_id
                        ),
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
                ),
            },
        )


async def get_line_item_snapshot(
    document_id: str,
) -> dict[str, Any] | None:
    document_query = text(
        """
        select
            id,
            status,
            latest_invoice_extraction_id,
            line_item_count,
            line_item_confidence
        from public.documents
        where id = cast(:document_id as uuid)
        """
    )

    extraction_query = text(
        """
        select
            id,
            schema_version,
            status,
            line_item_count,
            line_item_confidence,
            started_at,
            completed_at
        from public.invoice_extractions
        where document_id =
            cast(:document_id as uuid)
        order by started_at desc
        limit 1
        """
    )

    items_query = text(
        """
        select
            id,
            line_number,
            description,
            supplier_sku,
            quantity,
            unit_of_measure,
            unit_price,
            tax_rate,
            line_total,
            currency,
            confidence,
            confidence_source,
            extraction_method,
            page_number,
            raw_row_text,
            normalized_values,
            field_evidence,
            row_evidence,
            created_at
        from public.invoice_line_items
        where invoice_extraction_id =
            cast(:invoice_extraction_id as uuid)
        order by line_number
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

        extraction_result = (
            await connection.execute(
                extraction_query,
                {
                    "document_id": (
                        document_id
                    ),
                },
            )
        )

        extraction = (
            extraction_result
            .mappings()
            .one_or_none()
        )

        if extraction is None:
            return {
                "document": (
                    _document_payload(
                        dict(document)
                    )
                ),
                "invoice_extraction": None,
                "line_items": [],
            }

        items_result = await connection.execute(
            items_query,
            {
                "invoice_extraction_id": str(
                    extraction["id"]
                ),
            },
        )

        rows = (
            items_result.mappings().all()
        )

    items = [
        _line_item_payload(
            dict(row)
        )
        for row in rows
    ]

    extraction_payload = dict(
        extraction
    )

    if (
        extraction_payload[
            "line_item_confidence"
        ]
        is not None
    ):
        extraction_payload[
            "line_item_confidence"
        ] = float(
            extraction_payload[
                "line_item_confidence"
            ]
        )

    return {
        "document": _document_payload(
            dict(document)
        ),
        "invoice_extraction": (
            extraction_payload
        ),
        "line_items": items,
    }


def _document_payload(
    document: dict[str, Any],
) -> dict[str, Any]:
    if (
        document.get(
            "line_item_confidence"
        )
        is not None
    ):
        document[
            "line_item_confidence"
        ] = float(
            document[
                "line_item_confidence"
            ]
        )

    return document


def _line_item_payload(
    item: dict[str, Any],
) -> dict[str, Any]:
    item["quantity"] = _decimal_plain(
        item["quantity"]
    )

    item["unit_price"] = _money_text(
        item["unit_price"]
    )

    item["tax_rate"] = _decimal_plain(
        item["tax_rate"]
    )

    item["line_total"] = _money_text(
        item["line_total"]
    )

    item["confidence"] = float(
        item["confidence"]
    )

    return item


def _decimal_plain(
    value: Decimal | None,
) -> str | None:
    if value is None:
        return None

    result = format(
        value,
        "f",
    )

    if "." in result:
        result = result.rstrip(
            "0"
        ).rstrip(".")

    return result or "0"


def _money_text(
    value: Decimal | None,
) -> str | None:
    if value is None:
        return None

    result = format(
        value,
        "f",
    )

    if "." not in result:
        return f"{result}.00"

    whole, fraction = result.split(
        ".",
        1,
    )

    fraction = fraction.rstrip(
        "0"
    )

    if len(fraction) < 2:
        fraction = fraction.ljust(
            2,
            "0",
        )

    return f"{whole}.{fraction}"