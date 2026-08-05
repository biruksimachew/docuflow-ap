from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import text

from app.db.database import engine
from app.security.dependencies import (
    get_current_user,
    require_roles,
)
from app.security.models import AuthenticatedUser


router = APIRouter(
    prefix="/dashboard",
    tags=["Operations Dashboard"],
)


DOCUMENT_STATUSES = {
    "UPLOADED",
    "RECEIVED",
    "STORED",
    "QUEUED",
    "PROCESSING",
    "PREPROCESSING",
    "OCR_IN_PROGRESS",
    "EXTRACTION_IN_PROGRESS",
    "VALIDATING",
    "MATCHING",
    "DECIDING",
    "AUTO_APPROVED",
    "REVIEW_REQUIRED",
    "REJECTED",
    "FAILED",
}

REVIEW_STATUSES = {
    "OPEN",
    "CLAIMED",
    "RESOLVED_APPROVED",
    "RESOLVED_REJECTED",
    "CANCELLED",
}


DOCUMENT_SORT_COLUMNS = {
    "created_at": "d.created_at",
    "updated_at": "d.updated_at",
    "vendor_name": "coalesce(h.vendor_name, '')",
    "invoice_number": "coalesce(h.invoice_number, '')",
    "total_amount": "h.total_amount",
}

REVIEW_SORT_COLUMNS = {
    "priority": (
        "case when rc.priority = 'HIGH' "
        "then 0 else 1 end"
    ),
    "created_at": "rc.created_at",
    "updated_at": "rc.updated_at",
    "total_amount": "h.total_amount",
}


@router.get("/overview")
async def operations_overview(
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    metrics_query = text(
        """
        select
            (
                select count(*)
                from public.documents
            ) as total_documents,
            (
                select count(*)
                from public.documents
                where status = 'AUTO_APPROVED'
            ) as auto_approved,
            (
                select count(*)
                from public.documents
                where status = 'REVIEW_REQUIRED'
            ) as review_required,
            (
                select count(*)
                from public.documents
                where status = 'REJECTED'
            ) as rejected,
            (
                select count(*)
                from public.documents
                where status = 'FAILED'
            ) as failed,
            (
                select count(*)
                from public.review_cases
                where status = 'OPEN'
            ) as open_reviews,
            (
                select count(*)
                from public.review_cases
                where status = 'CLAIMED'
            ) as claimed_reviews,
            (
                select count(*)
                from public.accounting_exports
                where status = 'READY'
            ) as ready_exports,
            (
                select count(*)
                from public.notification_deliveries
                where status in (
                    'PENDING',
                    'DELIVERING',
                    'RETRY_SCHEDULED'
                )
            ) as notifications_in_flight,
            (
                select count(*)
                from public.notification_deliveries
                where status = 'FAILED'
            ) as notification_failures
        """
    )

    recent_query = text(
        """
        select
            d.id,
            d.original_filename,
            d.status,
            d.source_channel,
            d.created_at,
            d.updated_at,
            d.validation_outcome,
            d.duplicate_outcome,
            d.vendor_match_outcome,
            d.po_match_outcome,
            d.decision_outcome,
            d.final_resolution_source,
            h.vendor_name,
            h.invoice_number,
            h.currency,
            h.total_amount
        from public.documents d
        left join public.invoice_headers h
            on h.invoice_extraction_id =
                d.latest_invoice_extraction_id
        order by d.created_at desc
        limit 8
        """
    )

    async with engine.connect() as connection:
        metrics_result = await connection.execute(
            metrics_query
        )
        metrics = dict(
            metrics_result.mappings().one()
        )

        recent_result = await connection.execute(
            recent_query
        )
        recent_documents = [
            _json_safe_dict(dict(row))
            for row in recent_result.mappings().all()
        ]

    total = int(
        metrics["total_documents"]
        or 0
    )
    approved = int(
        metrics["auto_approved"]
        or 0
    )

    metrics["approval_rate"] = (
        round(
            approved / total * 100,
            1,
        )
        if total
        else 0.0
    )

    return {
        "requested_by": _actor(
            current_user
        ),
        "metrics": _json_safe_dict(
            metrics
        ),
        "recent_documents": recent_documents,
    }


@router.get("/documents")
async def dashboard_documents(
    status_filter: str | None = Query(
        default=None,
        alias="status",
    ),
    search: str | None = Query(
        default=None,
        max_length=120,
    ),
    sort_by: Literal[
        "created_at",
        "updated_at",
        "vendor_name",
        "invoice_number",
        "total_amount",
    ] = Query(
        default="created_at",
    ),
    sort_direction: Literal[
        "asc",
        "desc",
    ] = Query(
        default="desc",
    ),
    limit: int = Query(
        default=25,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    normalized_status = (
        status_filter.strip().upper()
        if status_filter
        else ""
    )

    if (
        normalized_status
        and normalized_status
        not in DOCUMENT_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_DOCUMENT_STATUS",
                "message": (
                    "The requested document status is not supported."
                ),
                "allowed_statuses": sorted(
                    DOCUMENT_STATUSES
                ),
            },
        )

    normalized_search = (
        search.strip()
        if search
        else ""
    )

    where_clause = """
        where
            (
                :status_filter = ''
                or d.status = :status_filter
            )
            and (
                :search = ''
                or d.original_filename ilike
                    '%' || :search || '%'
                or coalesce(
                    h.vendor_name,
                    ''
                ) ilike
                    '%' || :search || '%'
                or coalesce(
                    h.invoice_number,
                    ''
                ) ilike
                    '%' || :search || '%'
            )
    """

    count_query = text(
        f"""
        select count(*)
        from public.documents d
        left join public.invoice_headers h
            on h.invoice_extraction_id =
                d.latest_invoice_extraction_id
        {where_clause}
        """
    )

    rows_query = text(
        f"""
        select
            d.id,
            d.original_filename,
            d.status,
            d.source_channel,
            d.created_at,
            d.updated_at,
            d.validation_outcome,
            d.blocking_validation_count,
            d.duplicate_outcome,
            d.business_duplicate_blocking,
            d.vendor_match_outcome,
            d.po_match_outcome,
            d.matching_blocking,
            d.decision_outcome,
            d.decision_reason_codes,
            d.latest_review_case_id,
            d.final_resolution_source,
            h.vendor_name,
            h.invoice_number,
            h.invoice_date,
            h.due_date,
            h.purchase_order_number,
            h.currency,
            h.total_amount
        from public.documents d
        left join public.invoice_headers h
            on h.invoice_extraction_id =
                d.latest_invoice_extraction_id
        {where_clause}
        order by
            {DOCUMENT_SORT_COLUMNS[sort_by]}
            {sort_direction},
            d.id {sort_direction}
        limit :limit
        offset :offset
        """
    )

    parameters = {
        "status_filter": normalized_status,
        "search": normalized_search,
        "limit": limit,
        "offset": offset,
    }

    async with engine.connect() as connection:
        count_result = await connection.execute(
            count_query,
            parameters,
        )
        total = int(
            count_result.scalar_one()
        )

        rows_result = await connection.execute(
            rows_query,
            parameters,
        )
        documents = [
            _json_safe_dict(dict(row))
            for row in rows_result.mappings().all()
        ]

    return {
        "requested_by": _actor(
            current_user
        ),
        "filters": {
            "status": (
                normalized_status
                or None
            ),
            "search": (
                normalized_search
                or None
            ),
            "sort_by": sort_by,
            "sort_direction": sort_direction,
        },
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total,
        },
        "documents": documents,
    }


@router.get("/documents/{document_id}")
async def dashboard_document_detail(
    document_id: UUID,
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    document_query = text(
        """
        select
            d.*,
            h.id as invoice_header_id,
            h.vendor_name,
            h.invoice_number,
            h.invoice_date,
            h.due_date,
            h.purchase_order_number,
            h.currency,
            h.subtotal,
            h.discount_amount,
            h.shipping_amount,
            h.tax_amount,
            h.total_amount
        from public.documents d
        left join public.invoice_headers h
            on h.invoice_extraction_id =
                d.latest_invoice_extraction_id
        where d.id =
            cast(:document_id as uuid)
        limit 1
        """
    )

    line_query = text(
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
            confidence
        from public.invoice_line_items
        where document_id =
            cast(:document_id as uuid)
        order by line_number
        """
    )

    decision_query = text(
        """
        select
            id,
            status,
            outcome,
            blocking,
            reason_codes,
            explanation,
            policy_version,
            started_at,
            completed_at
        from public.decision_runs
        where document_id =
            cast(:document_id as uuid)
        order by started_at desc
        limit 1
        """
    )

    review_query = text(
        """
        select
            id,
            status,
            priority,
            reason_codes,
            explanation,
            claimed_by_user_id,
            claimed_by_email,
            claimed_at,
            resolved_by_user_id,
            resolved_by_email,
            resolved_at,
            resolution_note,
            version,
            latest_control_run_id,
            created_at,
            updated_at
        from public.review_cases
        where document_id =
            cast(:document_id as uuid)
        order by created_at desc
        limit 1
        """
    )

    export_query = text(
        """
        select
            id,
            export_format,
            schema_version,
            source_kind,
            source_version,
            status,
            file_name,
            content_type,
            payload_sha256,
            row_count,
            requested_at,
            completed_at
        from public.accounting_exports
        where document_id =
            cast(:document_id as uuid)
        order by requested_at desc
        """
    )

    notification_query = text(
        """
        select
            id,
            accounting_export_id,
            channel,
            provider,
            destination,
            status,
            attempt_count,
            max_attempts,
            last_attempt_at,
            next_attempt_at,
            delivered_at,
            last_error_code,
            last_error_message,
            created_at,
            updated_at
        from public.notification_deliveries
        where document_id =
            cast(:document_id as uuid)
        order by created_at desc
        """
    )

    parameters = {
        "document_id": str(
            document_id
        )
    }

    async with engine.connect() as connection:
        document_result = await connection.execute(
            document_query,
            parameters,
        )
        document = (
            document_result
            .mappings()
            .one_or_none()
        )

        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": (
                        "The requested document does not exist."
                    ),
                },
            )

        lines_result = await connection.execute(
            line_query,
            parameters,
        )
        decision_result = await connection.execute(
            decision_query,
            parameters,
        )
        review_result = await connection.execute(
            review_query,
            parameters,
        )
        exports_result = await connection.execute(
            export_query,
            parameters,
        )
        notifications_result = await connection.execute(
            notification_query,
            parameters,
        )

        lines = [
            _json_safe_dict(dict(row))
            for row in lines_result.mappings().all()
        ]
        decision = (
            decision_result
            .mappings()
            .one_or_none()
        )
        review_case = (
            review_result
            .mappings()
            .one_or_none()
        )
        exports = [
            _json_safe_dict(dict(row))
            for row in exports_result.mappings().all()
        ]
        notifications = [
            _json_safe_dict(dict(row))
            for row in notifications_result.mappings().all()
        ]

    return {
        "requested_by": _actor(
            current_user
        ),
        "document": _json_safe_dict(
            dict(document)
        ),
        "line_items": lines,
        "decision": (
            _json_safe_dict(
                dict(decision)
            )
            if decision
            else None
        ),
        "review_case": (
            _json_safe_dict(
                dict(review_case)
            )
            if review_case
            else None
        ),
        "exports": exports,
        "notifications": notifications,
    }


@router.get("/reviews")
async def dashboard_reviews(
    status_filter: str | None = Query(
        default=None,
        alias="status",
    ),
    search: str | None = Query(
        default=None,
        max_length=120,
    ),
    owner: Literal[
        "ALL",
        "UNCLAIMED",
        "MINE",
        "CLAIMED",
    ] = Query(
        default="ALL",
    ),
    sort_by: Literal[
        "priority",
        "created_at",
        "updated_at",
        "total_amount",
    ] = Query(
        default="priority",
    ),
    sort_direction: Literal[
        "asc",
        "desc",
    ] = Query(
        default="asc",
    ),
    limit: int = Query(
        default=25,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "REVIEWER",
            "ADMIN",
        )
    ),
) -> dict[str, Any]:
    normalized_status = (
        status_filter.strip().upper()
        if status_filter
        else ""
    )

    if (
        normalized_status
        and normalized_status
        not in REVIEW_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_REVIEW_STATUS",
                "message": (
                    "The requested review status is not supported."
                ),
                "allowed_statuses": sorted(
                    REVIEW_STATUSES
                ),
            },
        )

    normalized_search = (
        search.strip()
        if search
        else ""
    )

    where_clause = """
        where
            (
                :status_filter = ''
                or rc.status = :status_filter
            )
            and (
                :search = ''
                or d.original_filename ilike
                    '%' || :search || '%'
                or coalesce(
                    h.vendor_name,
                    ''
                ) ilike
                    '%' || :search || '%'
                or coalesce(
                    h.invoice_number,
                    ''
                ) ilike
                    '%' || :search || '%'
            )
            and (
                :owner = 'ALL'
                or (
                    :owner = 'UNCLAIMED'
                    and rc.claimed_by_user_id is null
                )
                or (
                    :owner = 'CLAIMED'
                    and rc.claimed_by_user_id is not null
                )
                or (
                    :owner = 'MINE'
                    and rc.claimed_by_user_id =
                        cast(:current_user_id as uuid)
                )
            )
    """

    count_query = text(
        f"""
        select count(*)
        from public.review_cases rc
        join public.documents d
            on d.id = rc.document_id
        left join public.invoice_headers h
            on h.invoice_extraction_id =
                d.latest_invoice_extraction_id
        {where_clause}
        """
    )

    rows_query = text(
        f"""
        select
            rc.id,
            rc.document_id,
            rc.status,
            rc.priority,
            rc.reason_codes,
            rc.explanation,
            rc.claimed_by_user_id,
            rc.claimed_by_email,
            rc.claimed_at,
            rc.resolved_by_user_id,
            rc.resolved_by_email,
            rc.resolved_at,
            rc.version,
            rc.created_at,
            rc.updated_at,
            d.original_filename,
            d.status as document_status,
            h.vendor_name,
            h.invoice_number,
            h.currency,
            h.total_amount
        from public.review_cases rc
        join public.documents d
            on d.id = rc.document_id
        left join public.invoice_headers h
            on h.invoice_extraction_id =
                d.latest_invoice_extraction_id
        {where_clause}
        order by
            {REVIEW_SORT_COLUMNS[sort_by]}
            {sort_direction},
            rc.created_at asc,
            rc.id asc
        limit :limit
        offset :offset
        """
    )

    parameters = {
        "status_filter": normalized_status,
        "search": normalized_search,
        "owner": owner,
        "current_user_id": (
            current_user.user_id
        ),
        "limit": limit,
        "offset": offset,
    }

    async with engine.connect() as connection:
        count_result = await connection.execute(
            count_query,
            parameters,
        )
        total = int(
            count_result.scalar_one()
        )

        rows_result = await connection.execute(
            rows_query,
            parameters,
        )
        reviews = [
            _json_safe_dict(dict(row))
            for row in rows_result.mappings().all()
        ]

    return {
        "requested_by": _actor(
            current_user
        ),
        "filters": {
            "status": (
                normalized_status
                or None
            ),
            "search": (
                normalized_search
                or None
            ),
            "owner": owner,
            "sort_by": sort_by,
            "sort_direction": sort_direction,
        },
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total,
        },
        "reviews": reviews,
    }


def _actor(
    user: AuthenticatedUser,
) -> dict[str, str]:
    return {
        "user_id": user.user_id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
    }


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
