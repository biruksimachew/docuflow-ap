from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.db.database import engine
from app.security.models import AuthenticatedUser
from app.services.reviews.correction_policy import (
    can_manage_claimed_case,
)
from app.services.reviews.errors import (
    ReviewCaseAuthorizationError,
    ReviewCaseConflictError,
    ReviewCaseNotFoundError,
)


async def load_review_case_context(
    review_case_id: str,
) -> dict[str, Any] | None:
    query = text(
        """
        select
            review.*,
            document.status as document_status,
            decision.invoice_extraction_id
        from public.review_cases review
        join public.documents document
            on document.id = review.document_id
        join public.decision_runs decision
            on decision.id = review.decision_run_id
        where review.id =
            cast(:review_case_id as uuid)
        limit 1
        """
    )

    async with engine.connect() as connection:
        result = await connection.execute(
            query,
            {
                "review_case_id": review_case_id,
            },
        )

        row = result.mappings().one_or_none()

    return (
        dict(row)
        if row is not None
        else None
    )


async def load_effective_invoice(
    review_case_id: str,
) -> dict[str, Any]:
    context = await load_review_case_context(
        review_case_id
    )

    if context is None:
        raise ReviewCaseNotFoundError()

    header_query = text(
        """
        select
            id,
            document_id,
            invoice_extraction_id,
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

    corrections_query = text(
        """
        select
            id,
            target_type,
            line_item_id,
            field_name,
            corrected_value,
            reason,
            applied_by_user_id,
            applied_by_email,
            applied_at
        from public.review_corrections
        where
            review_case_id =
                cast(:review_case_id as uuid)
            and status = 'APPLIED'
        order by applied_at asc
        """
    )

    async with engine.connect() as connection:
        header_result = await connection.execute(
            header_query,
            {
                "invoice_extraction_id": str(
                    context[
                        "invoice_extraction_id"
                    ]
                ),
            },
        )

        header_row = (
            header_result
            .mappings()
            .one_or_none()
        )

        if header_row is None:
            raise RuntimeError(
                "The canonical invoice header was not found."
            )

        lines_result = await connection.execute(
            lines_query,
            {
                "invoice_extraction_id": str(
                    context[
                        "invoice_extraction_id"
                    ]
                ),
            },
        )

        correction_result = await connection.execute(
            corrections_query,
            {
                "review_case_id": review_case_id,
            },
        )

        line_rows = (
            lines_result
            .mappings()
            .all()
        )

        correction_rows = (
            correction_result
            .mappings()
            .all()
        )

    original_header = _json_safe_dict(
        dict(
            header_row
        )
    )

    original_lines = [
        _json_safe_dict(
            dict(row)
        )
        for row in line_rows
    ]

    effective_header = dict(
        original_header
    )

    effective_lines = [
        dict(line)
        for line in original_lines
    ]

    effective_lines_by_id = {
        str(line["id"]): line
        for line in effective_lines
    }

    applied_corrections: list[dict[str, Any]] = []

    for row in correction_rows:
        correction = _json_safe_dict(
            dict(row)
        )

        field_name = str(
            correction["field_name"]
        )

        if correction["target_type"] == "HEADER":
            effective_header[
                field_name
            ] = correction[
                "corrected_value"
            ]
        else:
            line_item_id = str(
                correction["line_item_id"]
            )

            line = effective_lines_by_id.get(
                line_item_id
            )

            if line is None:
                raise RuntimeError(
                    "An applied correction references "
                    "an unavailable invoice line."
                )

            line[
                field_name
            ] = correction[
                "corrected_value"
            ]

        applied_corrections.append(
            correction
        )

    return {
        "review_case": _json_safe_dict(
            context
        ),
        "original": {
            "header": original_header,
            "lines": original_lines,
        },
        "effective": {
            "header": effective_header,
            "lines": effective_lines,
        },
        "applied_corrections": (
            applied_corrections
        ),
    }


async def create_review_correction(
    *,
    review_case_id: str,
    actor: AuthenticatedUser,
    target_type: str,
    line_item_id: str | None,
    field_name: str,
    original_value: Any,
    corrected_value: Any,
    reason: str,
) -> dict[str, Any]:
    context = await load_review_case_context(
        review_case_id
    )

    if context is None:
        raise ReviewCaseNotFoundError()

    if context["status"] not in {
        "OPEN",
        "CLAIMED",
    }:
        raise ReviewCaseConflictError(
            "Corrections cannot be proposed for a closed review case."
        )

    query = text(
        """
        insert into public.review_corrections (
            review_case_id,
            document_id,
            target_type,
            line_item_id,
            field_name,
            original_value,
            corrected_value,
            reason,
            status,
            proposed_by_user_id,
            proposed_by_email,
            proposed_by_role
        )
        values (
            cast(:review_case_id as uuid),
            cast(:document_id as uuid),
            :target_type,
            cast(:line_item_id as uuid),
            :field_name,
            cast(:original_value as jsonb),
            cast(:corrected_value as jsonb),
            :reason,
            'PROPOSED',
            cast(:actor_user_id as uuid),
            :actor_email,
            :actor_role
        )
        returning *
        """
    )

    async with engine.begin() as connection:
        result = await connection.execute(
            query,
            {
                "review_case_id": review_case_id,
                "document_id": str(
                    context["document_id"]
                ),
                "target_type": target_type,
                "line_item_id": line_item_id,
                "field_name": field_name,
                "original_value": json.dumps(
                    original_value
                ),
                "corrected_value": json.dumps(
                    corrected_value
                ),
                "reason": reason,
                "actor_user_id": actor.user_id,
                "actor_email": actor.email,
                "actor_role": actor.role,
            },
        )

        correction = dict(
            result.mappings().one()
        )

        await _insert_event(
            connection=connection,
            review_case_id=review_case_id,
            document_id=str(
                context["document_id"]
            ),
            actor=actor,
            event_type="CORRECTION_PROPOSED",
            message=(
                f"A correction was proposed for "
                f"{target_type}.{field_name}."
            ),
            metadata={
                "correction_id": str(
                    correction["id"]
                ),
                "target_type": target_type,
                "line_item_id": line_item_id,
                "field_name": field_name,
                "original_value": original_value,
                "corrected_value": corrected_value,
                "reason": reason,
            },
        )

    return _json_safe_dict(
        correction
    )


async def apply_review_correction(
    *,
    review_case_id: str,
    correction_id: str,
    actor: AuthenticatedUser,
) -> dict[str, Any]:
    case_query = text(
        """
        select *
        from public.review_cases
        where id = cast(:review_case_id as uuid)
        for update
        """
    )

    correction_query = text(
        """
        select *
        from public.review_corrections
        where
            id = cast(:correction_id as uuid)
            and review_case_id =
                cast(:review_case_id as uuid)
        for update
        """
    )

    supersede_query = text(
        """
        update public.review_corrections
        set status = 'SUPERSEDED'
        where
            review_case_id =
                cast(:review_case_id as uuid)
            and status = 'APPLIED'
            and target_type = :target_type
            and field_name = :field_name
            and line_item_id is not distinct from
                cast(:line_item_id as uuid)
        """
    )

    apply_query = text(
        """
        update public.review_corrections
        set
            status = 'APPLIED',
            applied_by_user_id =
                cast(:actor_user_id as uuid),
            applied_by_email =
                :actor_email,
            applied_at = now()
        where id = cast(:correction_id as uuid)
        returning *
        """
    )

    increment_case = text(
        """
        update public.review_cases
        set version = version + 1
        where id = cast(:review_case_id as uuid)
        returning *
        """
    )

    async with engine.begin() as connection:
        case_result = await connection.execute(
            case_query,
            {
                "review_case_id": review_case_id,
            },
        )

        review_case = (
            case_result
            .mappings()
            .one_or_none()
        )

        if review_case is None:
            raise ReviewCaseNotFoundError()

        if review_case["status"] != "CLAIMED":
            raise ReviewCaseConflictError(
                "The review case must be claimed before "
                "a correction can be applied."
            )

        claimed_by_user_id = (
            str(
                review_case[
                    "claimed_by_user_id"
                ]
            )
            if review_case[
                "claimed_by_user_id"
            ] is not None
            else None
        )

        if not can_manage_claimed_case(
            actor_user_id=actor.user_id,
            actor_role=actor.role,
            claimed_by_user_id=(
                claimed_by_user_id
            ),
        ):
            raise ReviewCaseAuthorizationError(
                "Only the claiming reviewer or an administrator "
                "can apply this correction."
            )

        correction_result = await connection.execute(
            correction_query,
            {
                "correction_id": correction_id,
                "review_case_id": review_case_id,
            },
        )

        correction = (
            correction_result
            .mappings()
            .one_or_none()
        )

        if correction is None:
            raise ReviewCaseNotFoundError()

        if correction["status"] == "APPLIED":
            return _json_safe_dict(
                dict(correction)
            )

        if correction["status"] != "PROPOSED":
            raise ReviewCaseConflictError(
                "Only a proposed correction can be applied."
            )

        line_item_id = (
            str(correction["line_item_id"])
            if correction["line_item_id"]
            is not None
            else None
        )

        await connection.execute(
            supersede_query,
            {
                "review_case_id": review_case_id,
                "target_type": correction[
                    "target_type"
                ],
                "field_name": correction[
                    "field_name"
                ],
                "line_item_id": line_item_id,
            },
        )

        applied_result = await connection.execute(
            apply_query,
            {
                "correction_id": correction_id,
                "actor_user_id": actor.user_id,
                "actor_email": actor.email,
            },
        )

        applied = dict(
            applied_result.mappings().one()
        )

        case_update_result = await connection.execute(
            increment_case,
            {
                "review_case_id": review_case_id,
            },
        )

        updated_case = dict(
            case_update_result
            .mappings()
            .one()
        )

        await _insert_event(
            connection=connection,
            review_case_id=review_case_id,
            document_id=str(
                updated_case["document_id"]
            ),
            actor=actor,
            event_type="CORRECTION_APPLIED",
            message=(
                f"A correction was applied to "
                f"{applied['target_type']}."
                f"{applied['field_name']}."
            ),
            metadata={
                "correction_id": correction_id,
                "case_version": (
                    updated_case["version"]
                ),
                "target_type": (
                    applied["target_type"]
                ),
                "line_item_id": line_item_id,
                "field_name": (
                    applied["field_name"]
                ),
                "original_value": (
                    applied["original_value"]
                ),
                "corrected_value": (
                    applied["corrected_value"]
                ),
            },
        )

    return _json_safe_dict(
        applied
    )


async def reject_review_correction(
    *,
    review_case_id: str,
    correction_id: str,
    actor: AuthenticatedUser,
    rejection_reason: str,
) -> dict[str, Any]:
    case_query = text(
        """
        select *
        from public.review_cases
        where id = cast(:review_case_id as uuid)
        for update
        """
    )

    correction_query = text(
        """
        select *
        from public.review_corrections
        where
            id = cast(:correction_id as uuid)
            and review_case_id =
                cast(:review_case_id as uuid)
        for update
        """
    )

    update_query = text(
        """
        update public.review_corrections
        set
            status = 'REJECTED',
            rejected_by_user_id =
                cast(:actor_user_id as uuid),
            rejected_by_email =
                :actor_email,
            rejected_at = now(),
            rejection_reason =
                :rejection_reason
        where id = cast(:correction_id as uuid)
        returning *
        """
    )

    async with engine.begin() as connection:
        case_result = await connection.execute(
            case_query,
            {
                "review_case_id": review_case_id,
            },
        )

        review_case = (
            case_result
            .mappings()
            .one_or_none()
        )

        if review_case is None:
            raise ReviewCaseNotFoundError()

        claimed_by_user_id = (
            str(
                review_case[
                    "claimed_by_user_id"
                ]
            )
            if review_case[
                "claimed_by_user_id"
            ] is not None
            else None
        )

        if (
            review_case["status"] != "CLAIMED"
            or not can_manage_claimed_case(
                actor_user_id=actor.user_id,
                actor_role=actor.role,
                claimed_by_user_id=(
                    claimed_by_user_id
                ),
            )
        ):
            raise ReviewCaseAuthorizationError(
                "Only the claiming reviewer or an administrator "
                "can reject a correction."
            )

        correction_result = await connection.execute(
            correction_query,
            {
                "correction_id": correction_id,
                "review_case_id": review_case_id,
            },
        )

        correction = (
            correction_result
            .mappings()
            .one_or_none()
        )

        if correction is None:
            raise ReviewCaseNotFoundError()

        if correction["status"] != "PROPOSED":
            raise ReviewCaseConflictError(
                "Only a proposed correction can be rejected."
            )

        result = await connection.execute(
            update_query,
            {
                "correction_id": correction_id,
                "actor_user_id": actor.user_id,
                "actor_email": actor.email,
                "rejection_reason": (
                    rejection_reason
                ),
            },
        )

        rejected = dict(
            result.mappings().one()
        )

        await _insert_event(
            connection=connection,
            review_case_id=review_case_id,
            document_id=str(
                review_case["document_id"]
            ),
            actor=actor,
            event_type="CORRECTION_REJECTED",
            message=(
                "A proposed correction was rejected."
            ),
            metadata={
                "correction_id": correction_id,
                "rejection_reason": (
                    rejection_reason
                ),
            },
        )

    return _json_safe_dict(
        rejected
    )


async def list_review_corrections(
    review_case_id: str,
) -> list[dict[str, Any]]:
    query = text(
        """
        select *
        from public.review_corrections
        where review_case_id =
            cast(:review_case_id as uuid)
        order by proposed_at asc
        """
    )

    async with engine.connect() as connection:
        result = await connection.execute(
            query,
            {
                "review_case_id": review_case_id,
            },
        )

        rows = result.mappings().all()

    return [
        _json_safe_dict(
            dict(row)
        )
        for row in rows
    ]


async def find_effective_business_duplicate(
    *,
    document_id: str,
    vendor_name: str | None,
    invoice_number: str | None,
    invoice_date: str | None,
    currency: str | None,
    total_amount: str | None,
) -> dict[str, Any]:
    if (
        not vendor_name
        or not invoice_number
    ):
        return {
            "outcome": "CLEAR",
            "matched_document_id": None,
            "candidate_count": 0,
        }

    normalized_vendor = " ".join(
        vendor_name.upper().split()
    )

    normalized_invoice_number = "".join(
        invoice_number.upper().split()
    )

    query = text(
        """
        select
            document_id,
            vendor_name,
            invoice_number,
            invoice_date,
            currency,
            total_amount
        from public.invoice_headers
        where
            document_id <>
                cast(:document_id as uuid)
            and upper(
                regexp_replace(
                    trim(vendor_name),
                    '\\s+',
                    ' ',
                    'g'
                )
            ) = :vendor_name
            and upper(
                regexp_replace(
                    trim(invoice_number),
                    '\\s+',
                    '',
                    'g'
                )
            ) = :invoice_number
        """
    )

    async with engine.connect() as connection:
        result = await connection.execute(
            query,
            {
                "document_id": document_id,
                "vendor_name": normalized_vendor,
                "invoice_number": (
                    normalized_invoice_number
                ),
            },
        )

        candidates = result.mappings().all()

    if not candidates:
        return {
            "outcome": "CLEAR",
            "matched_document_id": None,
            "candidate_count": 0,
        }

    for candidate in candidates:
        candidate_date = (
            candidate["invoice_date"].isoformat()
            if candidate["invoice_date"]
            is not None
            else None
        )

        candidate_currency = (
            str(candidate["currency"]).upper()
            if candidate["currency"]
            is not None
            else None
        )

        candidate_total = (
            format(
                candidate["total_amount"],
                "f",
            )
            if candidate["total_amount"]
            is not None
            else None
        )

        exact = (
            candidate_date == invoice_date
            and candidate_currency
            == (
                currency.upper()
                if currency
                else None
            )
            and _same_decimal_text(
                candidate_total,
                total_amount,
            )
        )

        if exact:
            return {
                "outcome": (
                    "BUSINESS_DUPLICATE"
                ),
                "matched_document_id": str(
                    candidate["document_id"]
                ),
                "candidate_count": len(
                    candidates
                ),
            }

    return {
        "outcome": "POTENTIAL_DUPLICATE",
        "matched_document_id": str(
            candidates[0]["document_id"]
        ),
        "candidate_count": len(
            candidates
        ),
    }


async def start_review_control_run(
    *,
    review_case_id: str,
) -> dict[str, Any]:
    context = await load_review_case_context(
        review_case_id
    )

    if context is None:
        raise ReviewCaseNotFoundError()

    query = text(
        """
        insert into public.review_control_runs (
            review_case_id,
            document_id,
            case_version,
            policy_version,
            status
        )
        values (
            cast(:review_case_id as uuid),
            cast(:document_id as uuid),
            :case_version,
            'review-controls-v1',
            'STARTED'
        )
        returning *
        """
    )

    async with engine.begin() as connection:
        result = await connection.execute(
            query,
            {
                "review_case_id": review_case_id,
                "document_id": str(
                    context["document_id"]
                ),
                "case_version": int(
                    context["version"]
                ),
            },
        )

        run = dict(
            result.mappings().one()
        )

    return _json_safe_dict(
        run
    )


async def complete_review_control_run(
    *,
    control_run_id: str,
    review_case_id: str,
    outcome: str,
    validation_passed: bool,
    duplicate_outcome: str,
    vendor_outcome: str,
    po_outcome: str,
    blocking_reasons: list[str],
    effective_snapshot: dict[str, Any],
    check_results: dict[str, Any],
    actor: AuthenticatedUser,
) -> dict[str, Any]:
    update_run = text(
        """
        update public.review_control_runs
        set
            status = 'SUCCEEDED',
            outcome = :outcome,
            validation_passed =
                :validation_passed,
            duplicate_outcome =
                :duplicate_outcome,
            vendor_outcome =
                :vendor_outcome,
            po_outcome =
                :po_outcome,
            blocking_reasons =
                cast(:blocking_reasons as jsonb),
            effective_snapshot =
                cast(:effective_snapshot as jsonb),
            check_results =
                cast(:check_results as jsonb),
            error_code = null,
            error_message = null,
            completed_at = now()
        where id = cast(:control_run_id as uuid)
        returning *
        """
    )

    update_case = text(
        """
        update public.review_cases
        set latest_control_run_id =
            cast(:control_run_id as uuid)
        where id = cast(:review_case_id as uuid)
        returning document_id
        """
    )

    async with engine.begin() as connection:
        result = await connection.execute(
            update_run,
            {
                "control_run_id": (
                    control_run_id
                ),
                "outcome": outcome,
                "validation_passed": (
                    validation_passed
                ),
                "duplicate_outcome": (
                    duplicate_outcome
                ),
                "vendor_outcome": (
                    vendor_outcome
                ),
                "po_outcome": po_outcome,
                "blocking_reasons": json.dumps(
                    blocking_reasons
                ),
                "effective_snapshot": json.dumps(
                    effective_snapshot
                ),
                "check_results": json.dumps(
                    check_results
                ),
            },
        )

        run = dict(
            result.mappings().one()
        )

        case_result = await connection.execute(
            update_case,
            {
                "control_run_id": (
                    control_run_id
                ),
                "review_case_id": (
                    review_case_id
                ),
            },
        )

        document_id = str(
            case_result
            .mappings()
            .one()[
                "document_id"
            ]
        )

        await _insert_event(
            connection=connection,
            review_case_id=review_case_id,
            document_id=document_id,
            actor=actor,
            event_type="CONTROLS_RERUN",
            message=(
                "Corrected invoice controls were rerun."
            ),
            metadata={
                "control_run_id": (
                    control_run_id
                ),
                "policy_version": (
                    "review-controls-v1"
                ),
                "outcome": outcome,
                "validation_passed": (
                    validation_passed
                ),
                "duplicate_outcome": (
                    duplicate_outcome
                ),
                "vendor_outcome": (
                    vendor_outcome
                ),
                "po_outcome": po_outcome,
                "blocking_reasons": (
                    blocking_reasons
                ),
                "case_version": run[
                    "case_version"
                ],
            },
        )

    return _json_safe_dict(
        run
    )


async def fail_review_control_run(
    *,
    control_run_id: str,
    error_code: str,
    error_message: str,
) -> None:
    query = text(
        """
        update public.review_control_runs
        set
            status = 'FAILED',
            error_code = :error_code,
            error_message = :error_message,
            completed_at = now()
        where id = cast(:control_run_id as uuid)
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            query,
            {
                "control_run_id": (
                    control_run_id
                ),
                "error_code": error_code,
                "error_message": (
                    error_message
                ),
            },
        )


async def get_latest_review_control_run(
    review_case_id: str,
) -> dict[str, Any] | None:
    query = text(
        """
        select *
        from public.review_control_runs
        where review_case_id =
            cast(:review_case_id as uuid)
        order by started_at desc
        limit 1
        """
    )

    async with engine.connect() as connection:
        result = await connection.execute(
            query,
            {
                "review_case_id": review_case_id,
            },
        )

        row = result.mappings().one_or_none()

    return (
        _json_safe_dict(
            dict(row)
        )
        if row is not None
        else None
    )


async def _insert_event(
    *,
    connection,
    review_case_id: str,
    document_id: str,
    actor: AuthenticatedUser,
    event_type: str,
    message: str,
    metadata: dict[str, Any],
) -> None:
    query = text(
        """
        insert into public.review_case_events (
            review_case_id,
            document_id,
            actor_type,
            actor_user_id,
            actor_email,
            actor_role,
            event_type,
            message,
            metadata
        )
        values (
            cast(:review_case_id as uuid),
            cast(:document_id as uuid),
            'USER',
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
            "review_case_id": (
                review_case_id
            ),
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


def _json_safe_dict(
    value: dict[str, Any],
) -> dict[str, Any]:
    return {
        key: _json_safe(
            item
        )
        for key, item in value.items()
    }


def _json_safe(
    value: Any,
) -> Any:
    if isinstance(
        value,
        UUID,
    ):
        return str(
            value
        )

    if isinstance(
        value,
        Decimal,
    ):
        return format(
            value,
            "f",
        )

    if isinstance(
        value,
        (
            date,
            datetime,
        ),
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
        list,
    ):
        return [
            _json_safe(item)
            for item in value
        ]

    return value


def _same_decimal_text(
    left: str | None,
    right: str | None,
) -> bool:
    if (
        left is None
        or right is None
    ):
        return left == right

    try:
        return Decimal(left) == Decimal(right)
    except Exception:
        return False