from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.db.database import engine
from app.security.models import AuthenticatedUser
from app.services.reviews.errors import (
    ReviewCaseAuthorizationError,
    ReviewCaseConflictError,
    ReviewCaseNotFoundError,
)
from app.services.reviews.policy import (
    can_release_review_case,
)


async def ensure_review_case(
    *,
    document_id: str,
    decision_run_id: str,
    reason_codes: list[str],
    explanation: str,
) -> dict[str, Any]:
    existing_query = text(
        """
        select *
        from public.review_cases
        where
            document_id = cast(:document_id as uuid)
            and status in (
                'OPEN',
                'CLAIMED'
            )
        order by created_at desc
        limit 1
        """
    )

    insert_case = text(
        """
        insert into public.review_cases (
            document_id,
            decision_run_id,
            status,
            priority,
            reason_codes,
            explanation
        )
        values (
            cast(:document_id as uuid),
            cast(:decision_run_id as uuid),
            'OPEN',
            case
                when cast(:reason_codes as jsonb)
                    ? 'POTENTIAL_BUSINESS_DUPLICATE'
                then 'HIGH'
                else 'NORMAL'
            end,
            cast(:reason_codes as jsonb),
            :explanation
        )
        returning *
        """
    )

    update_document = text(
        """
        update public.documents
        set latest_review_case_id =
            cast(:review_case_id as uuid)
        where id = cast(:document_id as uuid)
        """
    )

    insert_event = text(
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
            'SYSTEM',
            null,
            null,
            null,
            'CREATED',
            :message,
            cast(:metadata as jsonb)
        )
        """
    )

    async with engine.begin() as connection:
        existing_result = await connection.execute(
            existing_query,
            {
                "document_id": document_id,
            },
        )

        existing = (
            existing_result
            .mappings()
            .one_or_none()
        )

        if existing is not None:
            return dict(existing)

        result = await connection.execute(
            insert_case,
            {
                "document_id": document_id,
                "decision_run_id": decision_run_id,
                "reason_codes": json.dumps(
                    reason_codes
                ),
                "explanation": explanation,
            },
        )

        review_case = dict(
            result.mappings().one()
        )

        review_case_id = str(
            review_case["id"]
        )

        await connection.execute(
            update_document,
            {
                "review_case_id": review_case_id,
                "document_id": document_id,
            },
        )

        await connection.execute(
            insert_event,
            {
                "review_case_id": review_case_id,
                "document_id": document_id,
                "message": (
                    "A human-review case was created "
                    "from the authoritative invoice decision."
                ),
                "metadata": json.dumps(
                    {
                        "decision_run_id": (
                            decision_run_id
                        ),
                        "reason_codes": (
                            reason_codes
                        ),
                        "priority": (
                            review_case[
                                "priority"
                            ]
                        ),
                    }
                ),
            },
        )

    return review_case


async def list_review_cases(
    *,
    status: str | None,
    document_id: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    query = text(
        """
        select
            review.id,
            review.document_id,
            review.decision_run_id,
            review.status,
            review.priority,
            review.reason_codes,
            review.explanation,
            review.claimed_by_user_id,
            review.claimed_by_email,
            review.claimed_at,
            review.version,
            review.created_at,
            review.updated_at,

            coalesce(
                to_jsonb(document) ->> 'filename',
                to_jsonb(document) ->> 'original_filename',
                to_jsonb(document) ->> 'source_filename',
                'unknown'
            ) as filename,
            document.source_channel,
            document.decision_outcome,
            document.decision_explanation,
            document.decided_at

        from public.review_cases review

        join public.documents document
            on document.id = review.document_id

        where
            (
                cast(:status as text) is null
                or review.status = cast(:status as text)
            )
            and (
                cast(:document_id as text) is null
                or review.document_id =
                    cast(:document_id as uuid)
            )

        order by
            case review.priority
                when 'HIGH' then 0
                else 1
            end,
            review.created_at asc

        limit :limit
        """
    )

    async with engine.connect() as connection:
        result = await connection.execute(
            query,
            {
                "status": status,
                "document_id": document_id,
                "limit": limit,
            },
        )

        rows = result.mappings().all()

    return [
        dict(row)
        for row in rows
    ]


async def get_review_case_snapshot(
    review_case_id: str,
) -> dict[str, Any] | None:
    case_query = text(
        """
        select
            review.*,
            coalesce(
                to_jsonb(document) ->> 'filename',
                to_jsonb(document) ->> 'original_filename',
                to_jsonb(document) ->> 'source_filename',
                'unknown'
            ) as filename,
            document.source_channel,
            document.status as document_status,
            document.decision_outcome,
            document.decision_reason_codes,
            document.decision_explanation,
            document.decided_at
        from public.review_cases review
        join public.documents document
            on document.id = review.document_id
        where review.id =
            cast(:review_case_id as uuid)
        limit 1
        """
    )

    events_query = text(
        """
        select
            id,
            actor_type,
            actor_user_id,
            actor_email,
            actor_role,
            event_type,
            message,
            metadata,
            created_at
        from public.review_case_events
        where review_case_id =
            cast(:review_case_id as uuid)
        order by created_at asc
        """
    )

    async with engine.connect() as connection:
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
            return None

        event_result = await connection.execute(
            events_query,
            {
                "review_case_id": review_case_id,
            },
        )

        events = [
            dict(row)
            for row in (
                event_result
                .mappings()
                .all()
            )
        ]

    return {
        "review_case": dict(
            review_case
        ),
        "events": events,
    }


async def claim_review_case(
    *,
    review_case_id: str,
    actor: AuthenticatedUser,
) -> dict[str, Any]:
    load_query = text(
        """
        select *
        from public.review_cases
        where id = cast(:review_case_id as uuid)
        for update
        """
    )

    update_query = text(
        """
        update public.review_cases
        set
            status = 'CLAIMED',
            claimed_by_user_id =
                cast(:actor_user_id as uuid),
            claimed_by_email =
                :actor_email,
            claimed_at = now(),
            version = version + 1
        where
            id = cast(:review_case_id as uuid)
            and status = 'OPEN'
        returning *
        """
    )

    async with engine.begin() as connection:
        current_result = await connection.execute(
            load_query,
            {
                "review_case_id": review_case_id,
            },
        )

        current = (
            current_result
            .mappings()
            .one_or_none()
        )

        if current is None:
            raise ReviewCaseNotFoundError()

        if (
            current["status"] == "CLAIMED"
            and str(current["claimed_by_user_id"])
            == actor.user_id
        ):
            return dict(current)

        if current["status"] != "OPEN":
            raise ReviewCaseConflictError(
                "The review case is not available for claiming."
            )

        result = await connection.execute(
            update_query,
            {
                "review_case_id": review_case_id,
                "actor_user_id": actor.user_id,
                "actor_email": actor.email,
            },
        )

        claimed = dict(
            result.mappings().one()
        )

        await _insert_user_event(
            connection=connection,
            review_case=claimed,
            actor=actor,
            event_type="CLAIMED",
            message=(
                "The review case was claimed."
            ),
            metadata={
                "case_version": (
                    claimed["version"]
                ),
            },
        )

    return claimed


async def release_review_case(
    *,
    review_case_id: str,
    actor: AuthenticatedUser,
) -> dict[str, Any]:
    load_query = text(
        """
        select *
        from public.review_cases
        where id = cast(:review_case_id as uuid)
        for update
        """
    )

    update_query = text(
        """
        update public.review_cases
        set
            status = 'OPEN',
            claimed_by_user_id = null,
            claimed_by_email = null,
            claimed_at = null,
            version = version + 1
        where id = cast(:review_case_id as uuid)
        returning *
        """
    )

    async with engine.begin() as connection:
        current_result = await connection.execute(
            load_query,
            {
                "review_case_id": review_case_id,
            },
        )

        current = (
            current_result
            .mappings()
            .one_or_none()
        )

        if current is None:
            raise ReviewCaseNotFoundError()

        if current["status"] == "OPEN":
            return dict(current)

        if current["status"] != "CLAIMED":
            raise ReviewCaseConflictError(
                "Only a claimed review case can be released."
            )

        if not can_release_review_case(
            actor_user_id=actor.user_id,
            actor_role=actor.role,
            claimed_by_user_id=(
                str(current["claimed_by_user_id"])
                if current["claimed_by_user_id"]
                is not None
                else None
            ),
        ):
            raise ReviewCaseAuthorizationError(
                "Only the claiming reviewer or an administrator "
                "can release this review case."
            )

        result = await connection.execute(
            update_query,
            {
                "review_case_id": review_case_id,
            },
        )

        released = dict(
            result.mappings().one()
        )

        await _insert_user_event(
            connection=connection,
            review_case=released,
            actor=actor,
            event_type="RELEASED",
            message=(
                "The review case was released back to the queue."
            ),
            metadata={
                "case_version": (
                    released["version"]
                ),
            },
        )

    return released


async def add_review_note(
    *,
    review_case_id: str,
    actor: AuthenticatedUser,
    note: str,
) -> dict[str, Any]:
    load_query = text(
        """
        select *
        from public.review_cases
        where id = cast(:review_case_id as uuid)
        """
    )

    async with engine.begin() as connection:
        result = await connection.execute(
            load_query,
            {
                "review_case_id": review_case_id,
            },
        )

        review_case = (
            result
            .mappings()
            .one_or_none()
        )

        if review_case is None:
            raise ReviewCaseNotFoundError()

        if review_case["status"] not in {
            "OPEN",
            "CLAIMED",
        }:
            raise ReviewCaseConflictError(
                "Notes cannot be added to a closed review case."
            )

        event = await _insert_user_event(
            connection=connection,
            review_case=dict(
                review_case
            ),
            actor=actor,
            event_type="NOTE_ADDED",
            message=note,
            metadata={
                "note_length": len(
                    note
                ),
            },
        )

    return event


async def _insert_user_event(
    *,
    connection,
    review_case: dict[str, Any],
    actor: AuthenticatedUser,
    event_type: str,
    message: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
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
        returning *
        """
    )

    result = await connection.execute(
        query,
        {
            "review_case_id": str(
                review_case["id"]
            ),
            "document_id": str(
                review_case["document_id"]
            ),
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

    return dict(
        result.mappings().one()
    )