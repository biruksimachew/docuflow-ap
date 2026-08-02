from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.db.database import engine
from app.security.models import AuthenticatedUser
from app.services.accounting_exports.renderer import (
    SCHEMA_VERSION,
    build_idempotency_key,
    render_export,
)
from app.services.reviews.correction_repository import (
    load_effective_invoice,
)


class AccountingExportNotFoundError(
    Exception
):
    """The requested document or export does not exist."""


class AccountingExportConflictError(
    Exception
):
    """The document is not eligible for accounting export."""


async def generate_accounting_export(
    *,
    document_id: str,
    export_format: str,
    actor: AuthenticatedUser,
) -> dict[str, Any]:
    source = await _load_export_source(
        document_id
    )

    normalized_format = (
        export_format.strip().upper()
    )

    idempotency_key = build_idempotency_key(
        document_id=document_id,
        export_format=normalized_format,
        source_kind=source[
            "source_kind"
        ],
        source_version=source[
            "source_version"
        ],
    )

    export_record, created = (
        await _create_or_get_export(
            source=source,
            export_format=normalized_format,
            idempotency_key=idempotency_key,
            actor=actor,
        )
    )

    if (
        not created
        and export_record["status"]
        in {
            "READY",
            "STARTED",
        }
    ):
        return {
            "export": _public_export_record(
                export_record
            ),
            "idempotent_reuse": True,
        }

    export_id = str(
        export_record["id"]
    )

    try:
        rendered = render_export(
            export_id=export_id,
            export_format=normalized_format,
            source=source,
        )

        ready = await _complete_export(
            export_id=export_id,
            rendered=rendered,
            actor=actor,
        )

        return {
            "export": _public_export_record(
                ready
            ),
            "idempotent_reuse": False,
        }

    except Exception as exc:
        await _fail_export(
            export_id=export_id,
            actor=actor,
            error_code=type(exc).__name__,
            error_message=str(exc)[:2000],
        )

        raise


async def list_document_exports(
    document_id: str,
) -> list[dict[str, Any]]:
    query = text(
        """
        select
            id,
            document_id,
            review_case_id,
            decision_run_id,
            export_format,
            schema_version,
            source_kind,
            source_version,
            idempotency_key,
            status,
            file_name,
            content_type,
            payload_sha256,
            row_count,
            created_by_user_id,
            created_by_email,
            created_by_role,
            requested_at,
            completed_at,
            error_code,
            error_message,
            metadata
        from public.accounting_exports
        where document_id =
            cast(:document_id as uuid)
        order by requested_at desc
        """
    )

    async with engine.connect() as connection:
        result = await connection.execute(
            query,
            {
                "document_id": document_id,
            },
        )

        rows = result.mappings().all()

    return [
        _json_safe_dict(
            dict(row)
        )
        for row in rows
    ]


async def get_export_snapshot(
    export_id: str,
) -> dict[str, Any]:
    export_query = text(
        """
        select
            id,
            document_id,
            review_case_id,
            decision_run_id,
            export_format,
            schema_version,
            source_kind,
            source_version,
            idempotency_key,
            status,
            file_name,
            content_type,
            payload_sha256,
            row_count,
            created_by_user_id,
            created_by_email,
            created_by_role,
            requested_at,
            completed_at,
            error_code,
            error_message,
            metadata
        from public.accounting_exports
        where id =
            cast(:export_id as uuid)
        limit 1
        """
    )

    events_query = text(
        """
        select
            id,
            actor_user_id,
            actor_email,
            actor_role,
            event_type,
            message,
            metadata,
            created_at
        from public.accounting_export_events
        where accounting_export_id =
            cast(:export_id as uuid)
        order by created_at asc
        """
    )

    async with engine.connect() as connection:
        result = await connection.execute(
            export_query,
            {
                "export_id": export_id,
            },
        )

        export_row = (
            result.mappings().one_or_none()
        )

        if export_row is None:
            raise AccountingExportNotFoundError()

        event_result = await connection.execute(
            events_query,
            {
                "export_id": export_id,
            },
        )

        events = event_result.mappings().all()

    return {
        "export": _json_safe_dict(
            dict(export_row)
        ),
        "events": [
            _json_safe_dict(
                dict(row)
            )
            for row in events
        ],
    }


async def download_accounting_export(
    *,
    export_id: str,
    actor: AuthenticatedUser,
) -> dict[str, Any]:
    query = text(
        """
        select *
        from public.accounting_exports
        where id =
            cast(:export_id as uuid)
        limit 1
        """
    )

    async with engine.begin() as connection:
        result = await connection.execute(
            query,
            {
                "export_id": export_id,
            },
        )

        row = result.mappings().one_or_none()

        if row is None:
            raise AccountingExportNotFoundError()

        export_record = dict(row)

        if export_record["status"] != "READY":
            raise AccountingExportConflictError(
                "The accounting export is not ready for download."
            )

        await _insert_event(
            connection=connection,
            export_id=export_id,
            document_id=str(
                export_record["document_id"]
            ),
            actor=actor,
            event_type="DOWNLOADED",
            message=(
                "The accounting export was downloaded."
            ),
            metadata={
                "export_format": export_record[
                    "export_format"
                ],
                "file_name": export_record[
                    "file_name"
                ],
                "payload_sha256": export_record[
                    "payload_sha256"
                ],
            },
        )

    return _json_safe_dict(
        export_record
    )


async def _load_export_source(
    document_id: str,
) -> dict[str, Any]:
    query = text(
        """
        select
            document.id,
            document.status,
            document.original_filename,
            document.sha256,
            document.latest_invoice_extraction_id,
            document.latest_decision_run_id,
            document.latest_review_case_id,
            document.final_resolution_source,
            review.status as review_case_status,
            review.version as review_case_version
        from public.documents document
        left join public.review_cases review
            on review.id =
                document.latest_review_case_id
        where document.id =
            cast(:document_id as uuid)
        limit 1
        """
    )

    async with engine.connect() as connection:
        result = await connection.execute(
            query,
            {
                "document_id": document_id,
            },
        )

        document = (
            result.mappings().one_or_none()
        )

    if document is None:
        raise AccountingExportNotFoundError()

    if document["status"] != "AUTO_APPROVED":
        raise AccountingExportConflictError(
            "Only approved invoices can be exported."
        )

    common = {
        "document_id": document_id,
        "original_filename": document[
            "original_filename"
        ],
        "document_sha256": document[
            "sha256"
        ],
        "decision_run_id": (
            str(
                document[
                    "latest_decision_run_id"
                ]
            )
            if document[
                "latest_decision_run_id"
            ] is not None
            else None
        ),
    }

    if (
        document[
            "final_resolution_source"
        ]
        == "MANUAL"
    ):
        if (
            document[
                "latest_review_case_id"
            ] is None
            or document[
                "review_case_status"
            ] != "RESOLVED_APPROVED"
        ):
            raise AccountingExportConflictError(
                "The manually approved invoice has no resolved approved review case."
            )

        review_case_id = str(
            document[
                "latest_review_case_id"
            ]
        )

        effective = await load_effective_invoice(
            review_case_id
        )

        return {
            **common,
            "source_kind": "CORRECTED",
            "source_version": (
                f"review-case:{review_case_id}:"
                f"v{document['review_case_version']}"
            ),
            "review_case_id": review_case_id,
            "invoice": effective[
                "effective"
            ],
        }

    if (
        document[
            "latest_invoice_extraction_id"
        ] is None
        or document[
            "latest_decision_run_id"
        ] is None
    ):
        raise AccountingExportConflictError(
            "The approved invoice has no authoritative extraction and decision."
        )

    invoice = await _load_canonical_invoice(
        invoice_extraction_id=str(
            document[
                "latest_invoice_extraction_id"
            ]
        )
    )

    return {
        **common,
        "source_kind": "CANONICAL",
        "source_version": (
            "decision-run:"
            + str(
                document[
                    "latest_decision_run_id"
                ]
            )
        ),
        "review_case_id": None,
        "invoice": invoice,
    }


async def _load_canonical_invoice(
    *,
    invoice_extraction_id: str,
) -> dict[str, Any]:
    header_query = text(
        """
        select
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
        from public.invoice_headers
        where invoice_extraction_id =
            cast(:invoice_extraction_id as uuid)
        limit 1
        """
    )

    lines_query = text(
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
            currency
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
                "invoice_extraction_id": (
                    invoice_extraction_id
                ),
            },
        )

        header = (
            header_result.mappings().one_or_none()
        )

        if header is None:
            raise AccountingExportConflictError(
                "The approved invoice header was not found."
            )

        lines_result = await connection.execute(
            lines_query,
            {
                "invoice_extraction_id": (
                    invoice_extraction_id
                ),
            },
        )

        lines = lines_result.mappings().all()

    return {
        "header": _json_safe_dict(
            dict(header)
        ),
        "lines": [
            _json_safe_dict(
                dict(row)
            )
            for row in lines
        ],
    }


async def _create_or_get_export(
    *,
    source: dict[str, Any],
    export_format: str,
    idempotency_key: str,
    actor: AuthenticatedUser,
) -> tuple[dict[str, Any], bool]:
    insert_query = text(
        """
        insert into public.accounting_exports (
            document_id,
            review_case_id,
            decision_run_id,
            export_format,
            schema_version,
            source_kind,
            source_version,
            idempotency_key,
            status,
            created_by_user_id,
            created_by_email,
            created_by_role,
            metadata
        )
        values (
            cast(:document_id as uuid),
            cast(:review_case_id as uuid),
            cast(:decision_run_id as uuid),
            :export_format,
            :schema_version,
            :source_kind,
            :source_version,
            :idempotency_key,
            'STARTED',
            cast(:actor_user_id as uuid),
            :actor_email,
            :actor_role,
            cast(:metadata as jsonb)
        )
        on conflict (idempotency_key)
        do nothing
        returning *
        """
    )

    select_query = text(
        """
        select *
        from public.accounting_exports
        where idempotency_key =
            :idempotency_key
        limit 1
        """
    )

    async with engine.begin() as connection:
        result = await connection.execute(
            insert_query,
            {
                "document_id": source[
                    "document_id"
                ],
                "review_case_id": source.get(
                    "review_case_id"
                ),
                "decision_run_id": source.get(
                    "decision_run_id"
                ),
                "export_format": export_format,
                "schema_version": SCHEMA_VERSION,
                "source_kind": source[
                    "source_kind"
                ],
                "source_version": source[
                    "source_version"
                ],
                "idempotency_key": idempotency_key,
                "actor_user_id": actor.user_id,
                "actor_email": actor.email,
                "actor_role": actor.role,
                "metadata": json.dumps(
                    {
                        "source_kind": source[
                            "source_kind"
                        ],
                        "source_version": source[
                            "source_version"
                        ],
                    }
                ),
            },
        )

        inserted = (
            result.mappings().one_or_none()
        )

        if inserted is not None:
            record = dict(
                inserted
            )

            await _insert_event(
                connection=connection,
                export_id=str(
                    record["id"]
                ),
                document_id=source[
                    "document_id"
                ],
                actor=actor,
                event_type="REQUESTED",
                message=(
                    "An accounting export was requested."
                ),
                metadata={
                    "export_format": export_format,
                    "schema_version": SCHEMA_VERSION,
                    "source_kind": source[
                        "source_kind"
                    ],
                    "source_version": source[
                        "source_version"
                    ],
                },
            )

            return (
                _json_safe_dict(record),
                True,
            )

        existing_result = await connection.execute(
            select_query,
            {
                "idempotency_key": (
                    idempotency_key
                ),
            },
        )

        existing = dict(
            existing_result.mappings().one()
        )

    return (
        _json_safe_dict(existing),
        False,
    )


async def _complete_export(
    *,
    export_id: str,
    rendered: dict[str, Any],
    actor: AuthenticatedUser,
) -> dict[str, Any]:
    update_query = text(
        """
        update public.accounting_exports
        set
            status = 'READY',
            file_name = :file_name,
            content_type = :content_type,
            payload_text = :payload_text,
            payload_sha256 = :payload_sha256,
            row_count = :row_count,
            completed_at = now(),
            error_code = null,
            error_message = null
        where id =
            cast(:export_id as uuid)
        returning *
        """
    )

    async with engine.begin() as connection:
        result = await connection.execute(
            update_query,
            {
                "export_id": export_id,
                "file_name": rendered[
                    "file_name"
                ],
                "content_type": rendered[
                    "content_type"
                ],
                "payload_text": rendered[
                    "payload_text"
                ],
                "payload_sha256": rendered[
                    "payload_sha256"
                ],
                "row_count": rendered[
                    "row_count"
                ],
            },
        )

        record = dict(
            result.mappings().one()
        )

        await _insert_event(
            connection=connection,
            export_id=export_id,
            document_id=str(
                record["document_id"]
            ),
            actor=actor,
            event_type="GENERATED",
            message=(
                "The accounting export was generated."
            ),
            metadata={
                "file_name": record[
                    "file_name"
                ],
                "content_type": record[
                    "content_type"
                ],
                "payload_sha256": record[
                    "payload_sha256"
                ],
                "row_count": record[
                    "row_count"
                ],
            },
        )

    return _json_safe_dict(
        record
    )


async def _fail_export(
    *,
    export_id: str,
    actor: AuthenticatedUser,
    error_code: str,
    error_message: str,
) -> None:
    update_query = text(
        """
        update public.accounting_exports
        set
            status = 'FAILED',
            error_code = :error_code,
            error_message = :error_message,
            completed_at = now()
        where id =
            cast(:export_id as uuid)
        returning document_id
        """
    )

    async with engine.begin() as connection:
        result = await connection.execute(
            update_query,
            {
                "export_id": export_id,
                "error_code": error_code,
                "error_message": error_message,
            },
        )

        row = result.mappings().one_or_none()

        if row is not None:
            await _insert_event(
                connection=connection,
                export_id=export_id,
                document_id=str(
                    row["document_id"]
                ),
                actor=actor,
                event_type="FAILED",
                message=(
                    "The accounting export generation failed."
                ),
                metadata={
                    "error_code": error_code,
                    "error_message": error_message,
                },
            )


async def _insert_event(
    *,
    connection,
    export_id: str,
    document_id: str,
    actor: AuthenticatedUser,
    event_type: str,
    message: str,
    metadata: dict[str, Any],
) -> None:
    query = text(
        """
        insert into public.accounting_export_events (
            accounting_export_id,
            document_id,
            actor_user_id,
            actor_email,
            actor_role,
            event_type,
            message,
            metadata
        )
        values (
            cast(:export_id as uuid),
            cast(:document_id as uuid),
            cast(:actor_user_id as uuid),
            :actor_email,
            :actor_role,
            :event_type,
            :message,
            cast(:metadata as jsonb)
        )
        """
    )

    await connection.execute(
        query,
        {
            "export_id": export_id,
            "document_id": document_id,
            "actor_user_id": actor.user_id,
            "actor_email": actor.email,
            "actor_role": actor.role,
            "event_type": event_type,
            "message": message,
            "metadata": json.dumps(
                metadata
            ),
        },
    )


def _public_export_record(
    value: dict[str, Any],
) -> dict[str, Any]:
    record = dict(
        value
    )

    record.pop(
        "payload_text",
        None,
    )

    return record


def _json_safe_dict(
    value: dict[str, Any],
) -> dict[str, Any]:
    return {
        key: _json_safe(item)
        for key, item in value.items()
    }


def _json_safe(
    value: Any,
) -> Any:
    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, Decimal):
        return format(value, "f")

    if isinstance(
        value,
        (
            date,
            datetime,
        ),
    ):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            key: _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _json_safe(item)
            for item in value
        ]

    return value
