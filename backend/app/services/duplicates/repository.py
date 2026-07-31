from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from app.db.database import engine
from app.services.duplicates.models import (
    BusinessInvoiceIdentity,
    DuplicateDetectionResult,
)


async def load_business_identity(
    *,
    document_id: str,
    invoice_extraction_id: str,
) -> BusinessInvoiceIdentity:
    query = text(
        """
        select
            header.document_id,
            header.invoice_extraction_id,
            header.vendor_name,
            header.invoice_number,
            header.invoice_date,
            header.currency,
            header.total_amount
        from public.invoice_headers header
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
            "Canonical invoice identity was not found "
            "for duplicate detection."
        )

    return _identity_from_row(
        row
    )


async def load_candidate_identities(
    *,
    current_document_id: str,
    invoice_number: str | None,
) -> tuple[BusinessInvoiceIdentity, ...]:
    if not invoice_number:
        return ()

    query = text(
        """
        select distinct on (header.document_id)
            header.document_id,
            header.invoice_extraction_id,
            header.vendor_name,
            header.invoice_number,
            header.invoice_date,
            header.currency,
            header.total_amount
        from public.invoice_headers header
        join public.invoice_extractions extraction
            on extraction.id =
                header.invoice_extraction_id
        where
            header.document_id
                <> cast(:current_document_id as uuid)
            and header.invoice_number =
                :invoice_number
            and extraction.status =
                'SUCCEEDED'
        order by
            header.document_id,
            header.created_at desc
        """
    )

    async with engine.connect() as connection:
        result = await connection.execute(
            query,
            {
                "current_document_id": (
                    current_document_id
                ),
                "invoice_number": (
                    invoice_number
                ),
            },
        )

        rows = result.mappings().all()

    return tuple(
        _identity_from_row(row)
        for row in rows
    )


async def start_duplicate_check(
    *,
    document_id: str,
    processing_run_id: str,
    invoice_extraction_id: str,
) -> str:
    duplicate_check_id = str(
        uuid4()
    )

    query = text(
        """
        insert into public.duplicate_checks (
            id,
            document_id,
            processing_run_id,
            invoice_extraction_id,
            ruleset_version,
            status
        )
        values (
            cast(:duplicate_check_id as uuid),
            cast(:document_id as uuid),
            cast(:processing_run_id as uuid),
            cast(:invoice_extraction_id as uuid),
            'business-duplicate-v1',
            'STARTED'
        )
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            query,
            {
                "duplicate_check_id": (
                    duplicate_check_id
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

    return duplicate_check_id


async def complete_duplicate_check(
    *,
    duplicate_check_id: str,
    document_id: str,
    result: DuplicateDetectionResult,
) -> None:
    insert_candidate = text(
        """
        insert into public.duplicate_candidates (
            duplicate_check_id,
            document_id,
            candidate_document_id,
            candidate_invoice_extraction_id,
            outcome,
            match_score,
            field_matches,
            current_values,
            candidate_values
        )
        values (
            cast(:duplicate_check_id as uuid),
            cast(:document_id as uuid),
            cast(:candidate_document_id as uuid),
            cast(:candidate_invoice_extraction_id as uuid),
            :outcome,
            :match_score,
            cast(:field_matches as jsonb),
            cast(:current_values as jsonb),
            cast(:candidate_values as jsonb)
        )
        """
    )

    complete_check = text(
        """
        update public.duplicate_checks
        set
            status = 'SUCCEEDED',
            outcome = :outcome,
            blocking = :blocking,
            candidate_count = :candidate_count,
            exact_match_count = :exact_match_count,
            potential_match_count =
                :potential_match_count,
            matched_document_id =
                cast(:matched_document_id as uuid),
            matched_invoice_extraction_id =
                cast(:matched_invoice_extraction_id as uuid),
            input_fingerprint =
                cast(:input_fingerprint as jsonb),
            error_code = null,
            error_message = null,
            completed_at = now()
        where id =
            cast(:duplicate_check_id as uuid)
        """
    )

    update_document = text(
        """
        update public.documents
        set
            latest_duplicate_check_id =
                cast(:duplicate_check_id as uuid),
            duplicate_outcome = :outcome,
            business_duplicate_blocking =
                :blocking,
            matched_duplicate_document_id =
                cast(:matched_document_id as uuid)
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
            'DOCUMENT_DUPLICATE_CHECK_COMPLETED',
            'SYSTEM',
            :reason,
            cast(:payload as jsonb)
        )
        """
    )

    async with engine.begin() as connection:
        for candidate in result.candidates:
            await connection.execute(
                insert_candidate,
                {
                    "duplicate_check_id": (
                        duplicate_check_id
                    ),
                    "document_id": document_id,
                    "candidate_document_id": (
                        candidate
                        .candidate_document_id
                    ),
                    "candidate_invoice_extraction_id": (
                        candidate
                        .candidate_invoice_extraction_id
                    ),
                    "outcome": (
                        candidate.outcome
                    ),
                    "match_score": Decimal(
                        str(
                            candidate.match_score
                        )
                    ),
                    "field_matches": json.dumps(
                        candidate.field_matches
                    ),
                    "current_values": json.dumps(
                        candidate.current_values
                    ),
                    "candidate_values": json.dumps(
                        candidate.candidate_values
                    ),
                },
            )

        parameters = {
            "duplicate_check_id": (
                duplicate_check_id
            ),
            "document_id": document_id,
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
            "input_fingerprint": json.dumps(
                result.input_fingerprint
            ),
        }

        await connection.execute(
            complete_check,
            parameters,
        )

        await connection.execute(
            update_document,
            parameters,
        )

        if result.outcome == "BUSINESS_DUPLICATE":
            reason = (
                "The canonical invoice exactly matches "
                "a previously processed business invoice."
            )
        elif result.outcome == "POTENTIAL_DUPLICATE":
            reason = (
                "The vendor and invoice number match a "
                "previous invoice, but one or more other "
                "identity fields differ."
            )
        else:
            reason = (
                "No previous business invoice matched "
                "the canonical duplicate identity."
            )

        await connection.execute(
            insert_audit,
            {
                "document_id": document_id,
                "reason": reason,
                "payload": json.dumps(
                    {
                        "duplicate_check_id": (
                            duplicate_check_id
                        ),
                        "ruleset_version": (
                            "business-duplicate-v1"
                        ),
                        "outcome": (
                            result.outcome
                        ),
                        "blocking": (
                            result.blocking
                        ),
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
                        "input_fingerprint": (
                            result.input_fingerprint
                        ),
                    }
                ),
            },
        )


async def fail_duplicate_check(
    *,
    duplicate_check_id: str,
    error_code: str,
    error_message: str,
) -> None:
    query = text(
        """
        update public.duplicate_checks
        set
            status = 'FAILED',
            error_code = :error_code,
            error_message = :error_message,
            completed_at = now()
        where id =
            cast(:duplicate_check_id as uuid)
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            query,
            {
                "duplicate_check_id": (
                    duplicate_check_id
                ),
                "error_code": error_code,
                "error_message": (
                    error_message
                ),
            },
        )


async def get_duplicate_snapshot(
    document_id: str,
) -> dict[str, Any] | None:
    document_query = text(
        """
        select
            id,
            status,
            duplicate_outcome,
            business_duplicate_blocking,
            latest_duplicate_check_id,
            matched_duplicate_document_id
        from public.documents
        where id = cast(:document_id as uuid)
        """
    )

    check_query = text(
        """
        select
            id,
            document_id,
            processing_run_id,
            invoice_extraction_id,
            ruleset_version,
            status,
            outcome,
            blocking,
            candidate_count,
            exact_match_count,
            potential_match_count,
            matched_document_id,
            matched_invoice_extraction_id,
            input_fingerprint,
            error_code,
            error_message,
            started_at,
            completed_at
        from public.duplicate_checks
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
            candidate_document_id,
            candidate_invoice_extraction_id,
            outcome,
            match_score,
            field_matches,
            current_values,
            candidate_values,
            created_at
        from public.duplicate_candidates
        where duplicate_check_id =
            cast(:duplicate_check_id as uuid)
        order by
            match_score desc,
            created_at
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

        check_result = await connection.execute(
            check_query,
            {
                "document_id": document_id,
            },
        )

        duplicate_check = (
            check_result
            .mappings()
            .one_or_none()
        )

        if duplicate_check is None:
            return {
                "document": dict(document),
                "duplicate_check": None,
                "candidates": [],
            }

        candidates_result = (
            await connection.execute(
                candidates_query,
                {
                    "duplicate_check_id": str(
                        duplicate_check["id"]
                    ),
                },
            )
        )

        candidate_rows = (
            candidates_result
            .mappings()
            .all()
        )

    candidates = []

    for row in candidate_rows:
        candidate = dict(row)

        candidate["match_score"] = float(
            candidate["match_score"]
        )

        candidates.append(
            candidate
        )

    return {
        "document": dict(document),
        "duplicate_check": dict(
            duplicate_check
        ),
        "candidates": candidates,
    }


def _identity_from_row(
    row,
) -> BusinessInvoiceIdentity:
    return BusinessInvoiceIdentity(
        document_id=str(
            row["document_id"]
        ),
        invoice_extraction_id=str(
            row["invoice_extraction_id"]
        ),
        vendor_name=row["vendor_name"],
        invoice_number=row["invoice_number"],
        invoice_date=row["invoice_date"],
        currency=(
            str(row["currency"]).strip()
            if row["currency"] is not None
            else None
        ),
        total_amount=_to_decimal(
            row["total_amount"]
        ),
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