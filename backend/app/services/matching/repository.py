from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from app.db.database import engine
from app.services.matching.engine import (
    normalize_name,
)
from app.services.matching.models import (
    InvoiceMatchInput,
    InvoiceMatchLine,
    PurchaseOrderLine,
    PurchaseOrderMatchResult,
    PurchaseOrderRecord,
    VendorCandidate,
    VendorMatchResult,
)


async def load_invoice_match_input(
    *,
    document_id: str,
    invoice_extraction_id: str,
) -> InvoiceMatchInput:
    header_query = text(
        """
        select
            document_id,
            invoice_extraction_id,
            vendor_name,
            purchase_order_number,
            currency,
            subtotal,
            tax_amount,
            total_amount
        from public.invoice_headers
        where
            document_id =
                cast(:document_id as uuid)
            and invoice_extraction_id =
                cast(:invoice_extraction_id as uuid)
        limit 1
        """
    )

    lines_query = text(
        """
        select
            line_number,
            description,
            quantity,
            unit_price,
            line_total
        from public.invoice_line_items
        where invoice_extraction_id =
            cast(:invoice_extraction_id as uuid)
        order by line_number
        """
    )

    async with engine.connect() as connection:
        header_result = await connection.execute(
            header_query,
            {
                "document_id": document_id,
                "invoice_extraction_id": (
                    invoice_extraction_id
                ),
            },
        )

        header = (
            header_result
            .mappings()
            .one_or_none()
        )

        if header is None:
            raise RuntimeError(
                "Canonical invoice header was not found "
                "for vendor and PO matching."
            )

        lines_result = await connection.execute(
            lines_query,
            {
                "invoice_extraction_id": (
                    invoice_extraction_id
                ),
            },
        )

        line_rows = (
            lines_result
            .mappings()
            .all()
        )

    lines = tuple(
        InvoiceMatchLine(
            line_number=int(
                row["line_number"]
            ),
            description=str(
                row["description"]
            ),
            normalized_description=(
                normalize_name(
                    str(
                        row["description"]
                    )
                )
            ),
            quantity=_to_decimal(
                row["quantity"]
            ),
            unit_price=_to_decimal(
                row["unit_price"]
            ),
            line_total=_to_decimal(
                row["line_total"]
            ),
        )
        for row in line_rows
    )

    return InvoiceMatchInput(
        document_id=document_id,
        invoice_extraction_id=(
            invoice_extraction_id
        ),
        vendor_name=header[
            "vendor_name"
        ],
        purchase_order_number=header[
            "purchase_order_number"
        ],
        currency=(
            str(header["currency"]).strip()
            if header["currency"] is not None
            else None
        ),
        subtotal=_to_decimal(
            header["subtotal"]
        ),
        tax_amount=_to_decimal(
            header["tax_amount"]
        ),
        total_amount=_to_decimal(
            header["total_amount"]
        ),
        lines=lines,
    )


async def load_vendor_candidates(
    normalized_input_name: str,
) -> tuple[VendorCandidate, ...]:
    query = text(
        """
        select distinct
            vendor.id,
            vendor.vendor_code,
            vendor.canonical_name,
            vendor.normalized_name,
            case
                when vendor.normalized_name =
                    :normalized_input_name
                then 'CANONICAL_NAME'
                else 'ALIAS'
            end as matched_on
        from public.vendors vendor
        left join public.vendor_aliases alias
            on alias.vendor_id = vendor.id
            and alias.active = true
        where
            vendor.status = 'ACTIVE'
            and (
                vendor.normalized_name =
                    :normalized_input_name
                or alias.normalized_alias =
                    :normalized_input_name
            )
        order by vendor.vendor_code
        """
    )

    async with engine.connect() as connection:
        result = await connection.execute(
            query,
            {
                "normalized_input_name": (
                    normalized_input_name
                ),
            },
        )

        rows = result.mappings().all()

    return tuple(
        VendorCandidate(
            vendor_id=str(
                row["id"]
            ),
            vendor_code=str(
                row["vendor_code"]
            ),
            canonical_name=str(
                row["canonical_name"]
            ),
            normalized_name=str(
                row["normalized_name"]
            ),
            matched_on=str(
                row["matched_on"]
            ),
        )
        for row in rows
    )


async def load_purchase_order(
    po_number: str | None,
) -> PurchaseOrderRecord | None:
    if not po_number:
        return None

    header_query = text(
        """
        select
            id,
            po_number,
            vendor_id,
            currency,
            status,
            subtotal,
            tax_amount,
            total_amount
        from public.purchase_orders
        where po_number = :po_number
        limit 1
        """
    )

    lines_query = text(
        """
        select
            line_number,
            description,
            normalized_description,
            quantity,
            unit_price,
            line_total
        from public.purchase_order_lines
        where purchase_order_id =
            cast(:purchase_order_id as uuid)
        order by line_number
        """
    )

    async with engine.connect() as connection:
        header_result = await connection.execute(
            header_query,
            {
                "po_number": (
                    po_number.strip().upper()
                ),
            },
        )

        header = (
            header_result
            .mappings()
            .one_or_none()
        )

        if header is None:
            return None

        lines_result = await connection.execute(
            lines_query,
            {
                "purchase_order_id": str(
                    header["id"]
                ),
            },
        )

        line_rows = (
            lines_result
            .mappings()
            .all()
        )

    lines = tuple(
        PurchaseOrderLine(
            line_number=int(
                row["line_number"]
            ),
            description=str(
                row["description"]
            ),
            normalized_description=str(
                row[
                    "normalized_description"
                ]
            ),
            quantity=_required_decimal(
                row["quantity"]
            ),
            unit_price=_required_decimal(
                row["unit_price"]
            ),
            line_total=_required_decimal(
                row["line_total"]
            ),
        )
        for row in line_rows
    )

    return PurchaseOrderRecord(
        purchase_order_id=str(
            header["id"]
        ),
        po_number=str(
            header["po_number"]
        ),
        vendor_id=str(
            header["vendor_id"]
        ),
        currency=str(
            header["currency"]
        ).strip(),
        status=str(
            header["status"]
        ),
        subtotal=_required_decimal(
            header["subtotal"]
        ),
        tax_amount=_required_decimal(
            header["tax_amount"]
        ),
        total_amount=_required_decimal(
            header["total_amount"]
        ),
        lines=lines,
    )


async def start_vendor_match_run(
    *,
    document_id: str,
    processing_run_id: str,
    invoice_extraction_id: str,
) -> str:
    run_id = str(
        uuid4()
    )

    query = text(
        """
        insert into public.vendor_match_runs (
            id,
            document_id,
            processing_run_id,
            invoice_extraction_id,
            ruleset_version,
            status
        )
        values (
            cast(:run_id as uuid),
            cast(:document_id as uuid),
            cast(:processing_run_id as uuid),
            cast(:invoice_extraction_id as uuid),
            'vendor-identity-v1',
            'STARTED'
        )
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            query,
            {
                "run_id": run_id,
                "document_id": document_id,
                "processing_run_id": (
                    processing_run_id
                ),
                "invoice_extraction_id": (
                    invoice_extraction_id
                ),
            },
        )

    return run_id


async def complete_vendor_match_run(
    *,
    run_id: str,
    document_id: str,
    result: VendorMatchResult,
) -> None:
    insert_candidate = text(
        """
        insert into public.vendor_match_candidates (
            vendor_match_run_id,
            vendor_id,
            vendor_code,
            canonical_name,
            matched_on,
            match_score,
            evidence
        )
        values (
            cast(:run_id as uuid),
            cast(:vendor_id as uuid),
            :vendor_code,
            :canonical_name,
            :matched_on,
            :match_score,
            cast(:evidence as jsonb)
        )
        """
    )

    complete_run = text(
        """
        update public.vendor_match_runs
        set
            status = 'SUCCEEDED',
            outcome = :outcome,
            blocking = :blocking,
            input_vendor_name =
                :input_vendor_name,
            normalized_input_name =
                :normalized_input_name,
            candidate_count =
                :candidate_count,
            matched_vendor_id =
                cast(:matched_vendor_id as uuid),
            evidence =
                cast(:evidence as jsonb),
            error_code = null,
            error_message = null,
            completed_at = now()
        where id = cast(:run_id as uuid)
        """
    )

    update_document = text(
        """
        update public.documents
        set
            latest_vendor_match_run_id =
                cast(:run_id as uuid),
            vendor_match_outcome =
                :outcome,
            resolved_vendor_id =
                cast(:matched_vendor_id as uuid)
        where id = cast(:document_id as uuid)
        """
    )

    async with engine.begin() as connection:
        for candidate in result.candidates:
            await connection.execute(
                insert_candidate,
                {
                    "run_id": run_id,
                    "vendor_id": (
                        candidate.vendor_id
                    ),
                    "vendor_code": (
                        candidate.vendor_code
                    ),
                    "canonical_name": (
                        candidate.canonical_name
                    ),
                    "matched_on": (
                        candidate.matched_on
                    ),
                    "match_score": Decimal(
                        "1.0000"
                    ),
                    "evidence": json.dumps(
                        {
                            "normalized_input_name": (
                                result
                                .normalized_input_name
                            ),
                            "candidate_normalized_name": (
                                candidate
                                .normalized_name
                            ),
                            "matched_on": (
                                candidate.matched_on
                            ),
                        }
                    ),
                },
            )

        parameters = {
            "run_id": run_id,
            "document_id": document_id,
            "outcome": result.outcome,
            "blocking": result.blocking,
            "input_vendor_name": (
                result.input_vendor_name
            ),
            "normalized_input_name": (
                result.normalized_input_name
            ),
            "candidate_count": len(
                result.candidates
            ),
            "matched_vendor_id": (
                result.matched_vendor_id
            ),
            "evidence": json.dumps(
                result.evidence
            ),
        }

        await connection.execute(
            complete_run,
            parameters,
        )

        await connection.execute(
            update_document,
            parameters,
        )


async def start_po_match_run(
    *,
    document_id: str,
    processing_run_id: str,
    invoice_extraction_id: str,
    vendor_match_run_id: str,
) -> str:
    run_id = str(
        uuid4()
    )

    query = text(
        """
        insert into public.po_match_runs (
            id,
            document_id,
            processing_run_id,
            invoice_extraction_id,
            vendor_match_run_id,
            ruleset_version,
            status
        )
        values (
            cast(:run_id as uuid),
            cast(:document_id as uuid),
            cast(:processing_run_id as uuid),
            cast(:invoice_extraction_id as uuid),
            cast(:vendor_match_run_id as uuid),
            'purchase-order-v1',
            'STARTED'
        )
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            query,
            {
                "run_id": run_id,
                "document_id": document_id,
                "processing_run_id": (
                    processing_run_id
                ),
                "invoice_extraction_id": (
                    invoice_extraction_id
                ),
                "vendor_match_run_id": (
                    vendor_match_run_id
                ),
            },
        )

    return run_id


async def complete_po_match_run(
    *,
    run_id: str,
    document_id: str,
    result: PurchaseOrderMatchResult,
) -> None:
    complete_run = text(
        """
        update public.po_match_runs
        set
            status = 'SUCCEEDED',
            outcome = :outcome,
            blocking = :blocking,
            input_po_number =
                :input_po_number,
            matched_purchase_order_id =
                cast(:matched_purchase_order_id as uuid),
            matched_line_count =
                :matched_line_count,
            mismatched_line_count =
                :mismatched_line_count,
            check_results =
                cast(:check_results as jsonb),
            error_code = null,
            error_message = null,
            completed_at = now()
        where id = cast(:run_id as uuid)
        """
    )

    update_document = text(
        """
        update public.documents
        set
            latest_po_match_run_id =
                cast(:run_id as uuid),
            po_match_outcome =
                :outcome,
            matched_purchase_order_id =
                cast(:matched_purchase_order_id as uuid),
            matching_blocking =
                :blocking
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
            'DOCUMENT_MATCHING_COMPLETED',
            'SYSTEM',
            :reason,
            cast(:payload as jsonb)
        )
        """
    )

    parameters = {
        "run_id": run_id,
        "document_id": document_id,
        "outcome": result.outcome,
        "blocking": result.blocking,
        "input_po_number": (
            result.input_po_number
        ),
        "matched_purchase_order_id": (
            result.matched_purchase_order_id
        ),
        "matched_line_count": (
            result.matched_line_count
        ),
        "mismatched_line_count": (
            result.mismatched_line_count
        ),
        "check_results": json.dumps(
            result.check_results
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

        reason = (
            "Vendor identity and purchase-order "
            "matching completed successfully."
            if result.outcome == "MATCHED"
            else (
                "Vendor identity or purchase-order "
                "matching requires review."
            )
        )

        await connection.execute(
            insert_audit,
            {
                "document_id": document_id,
                "reason": reason,
                "payload": json.dumps(
                    {
                        "po_match_run_id": run_id,
                        "ruleset_version": (
                            "purchase-order-v1"
                        ),
                        "outcome": (
                            result.outcome
                        ),
                        "blocking": (
                            result.blocking
                        ),
                        "matched_purchase_order_id": (
                            result
                            .matched_purchase_order_id
                        ),
                        "matched_line_count": (
                            result.matched_line_count
                        ),
                        "mismatched_line_count": (
                            result
                            .mismatched_line_count
                        ),
                    }
                ),
            },
        )


async def fail_vendor_match_run(
    *,
    run_id: str,
    error_code: str,
    error_message: str,
) -> None:
    await _fail_run(
        table_name="vendor_match_runs",
        run_id=run_id,
        error_code=error_code,
        error_message=error_message,
    )


async def fail_po_match_run(
    *,
    run_id: str,
    error_code: str,
    error_message: str,
) -> None:
    await _fail_run(
        table_name="po_match_runs",
        run_id=run_id,
        error_code=error_code,
        error_message=error_message,
    )


async def get_matching_snapshot(
    document_id: str,
) -> dict[str, Any] | None:
    document_query = text(
        """
        select
            id,
            status,
            vendor_match_outcome,
            resolved_vendor_id,
            po_match_outcome,
            matched_purchase_order_id,
            matching_blocking,
            latest_vendor_match_run_id,
            latest_po_match_run_id
        from public.documents
        where id = cast(:document_id as uuid)
        """
    )

    vendor_run_query = text(
        """
        select
            id,
            ruleset_version,
            status,
            outcome,
            blocking,
            input_vendor_name,
            normalized_input_name,
            candidate_count,
            matched_vendor_id,
            evidence,
            error_code,
            error_message,
            started_at,
            completed_at
        from public.vendor_match_runs
        where document_id =
            cast(:document_id as uuid)
        order by started_at desc
        limit 1
        """
    )

    candidates_query = text(
        """
        select
            id,
            vendor_id,
            vendor_code,
            canonical_name,
            matched_on,
            match_score,
            evidence,
            created_at
        from public.vendor_match_candidates
        where vendor_match_run_id =
            cast(:vendor_match_run_id as uuid)
        order by match_score desc
        """
    )

    po_run_query = text(
        """
        select
            id,
            ruleset_version,
            status,
            outcome,
            blocking,
            input_po_number,
            matched_purchase_order_id,
            matched_line_count,
            mismatched_line_count,
            check_results,
            error_code,
            error_message,
            started_at,
            completed_at
        from public.po_match_runs
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

        vendor_result = await connection.execute(
            vendor_run_query,
            {
                "document_id": document_id,
            },
        )

        vendor_run = (
            vendor_result
            .mappings()
            .one_or_none()
        )

        candidates: list[dict[str, Any]] = []

        if vendor_run is not None:
            candidate_result = (
                await connection.execute(
                    candidates_query,
                    {
                        "vendor_match_run_id": str(
                            vendor_run["id"]
                        ),
                    },
                )
            )

            for row in (
                candidate_result
                .mappings()
                .all()
            ):
                candidate = dict(row)

                candidate[
                    "match_score"
                ] = float(
                    candidate[
                        "match_score"
                    ]
                )

                candidates.append(
                    candidate
                )

        po_result = await connection.execute(
            po_run_query,
            {
                "document_id": document_id,
            },
        )

        po_run = (
            po_result
            .mappings()
            .one_or_none()
        )

    return {
        "document": dict(
            document
        ),
        "vendor_match": (
            dict(vendor_run)
            if vendor_run is not None
            else None
        ),
        "vendor_candidates": (
            candidates
        ),
        "purchase_order_match": (
            dict(po_run)
            if po_run is not None
            else None
        ),
    }


async def _fail_run(
    *,
    table_name: str,
    run_id: str,
    error_code: str,
    error_message: str,
) -> None:
    if table_name not in {
        "vendor_match_runs",
        "po_match_runs",
    }:
        raise ValueError(
            "Unsupported matching run table."
        )

    query = text(
        f"""
        update public.{table_name}
        set
            status = 'FAILED',
            error_code = :error_code,
            error_message = :error_message,
            completed_at = now()
        where id = cast(:run_id as uuid)
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            query,
            {
                "run_id": run_id,
                "error_code": error_code,
                "error_message": (
                    error_message
                ),
            },
        )


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


def _required_decimal(
    value: Any,
) -> Decimal:
    result = _to_decimal(
        value
    )

    if result is None:
        raise RuntimeError(
            "Required numeric master-data value is null."
        )

    return result