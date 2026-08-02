from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.db.database import engine
from app.security.models import AuthenticatedUser
from app.services.reviews.correction_policy import (
    approval_guard_reasons,
    can_manage_claimed_case,
    normalize_resolution_note,
)
from app.services.reviews.errors import (
    ReviewCaseAuthorizationError,
    ReviewCaseConflictError,
    ReviewCaseNotFoundError,
)


async def resolve_review_case(
    *,
    review_case_id: str,
    actor: AuthenticatedUser,
    resolution: str,
    note: str,
) -> dict[str, Any]:
    normalized_resolution = (
        resolution.strip().upper()
    )

    if normalized_resolution not in {
        "APPROVE",
        "REJECT",
    }:
        raise ValueError(
            "Resolution must be APPROVE or REJECT."
        )

    normalized_note = (
        normalize_resolution_note(
            note
        )
    )

    load_query = text(
        """
        select
            review.*,
            document.status as document_status,
            control.status as control_status,
            control.outcome as control_outcome,
            control.case_version
                as control_case_version,
            control.duplicate_outcome
                as control_duplicate_outcome,
            control.blocking_reasons
                as control_blocking_reasons
        from public.review_cases review
        join public.documents document
            on document.id = review.document_id
        left join public.review_control_runs control
            on control.id =
                review.latest_control_run_id
        where review.id =
            cast(:review_case_id as uuid)
        for update of review, document
        """
    )

    update_case = text(
        """
        update public.review_cases
        set
            status = :case_status,
            resolved_by_user_id =
                cast(:actor_user_id as uuid),
            resolved_by_email =
                :actor_email,
            resolved_at = now(),
            resolution_note =
                :resolution_note,
            version = version + 1
        where id =
            cast(:review_case_id as uuid)
        returning *
        """
    )

    update_document = text(
        """
        update public.documents
        set
            status = :document_status,
            final_resolution_source =
                'MANUAL',
            manual_resolution_note =
                :resolution_note,
            manual_resolved_by_user_id =
                cast(:actor_user_id as uuid),
            manual_resolved_by_email =
                :actor_email,
            manual_resolved_at = now()
        where id = cast(:document_id as uuid)
        returning *
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

    async with engine.begin() as connection:
        result = await connection.execute(
            load_query,
            {
                "review_case_id": (
                    review_case_id
                ),
            },
        )

        current = (
            result
            .mappings()
            .one_or_none()
        )

        if current is None:
            raise ReviewCaseNotFoundError()

        if current["status"] != "CLAIMED":
            raise ReviewCaseConflictError(
                "The review case must be claimed before resolution."
            )

        claimed_by_user_id = (
            str(
                current[
                    "claimed_by_user_id"
                ]
            )
            if current[
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
                "can resolve this review case."
            )

        guard_reasons: tuple[
            str,
            ...,
        ] = ()

        if normalized_resolution == "APPROVE":
            guard_reasons = (
                approval_guard_reasons(
                    document_status=str(
                        current[
                            "document_status"
                        ]
                    ),
                    case_version=int(
                        current["version"]
                    ),
                    control_case_version=(
                        int(
                            current[
                                "control_case_version"
                            ]
                        )
                        if current[
                            "control_case_version"
                        ] is not None
                        else None
                    ),
                    control_status=(
                        str(
                            current[
                                "control_status"
                            ]
                        )
                        if current[
                            "control_status"
                        ] is not None
                        else None
                    ),
                    control_outcome=(
                        str(
                            current[
                                "control_outcome"
                            ]
                        )
                        if current[
                            "control_outcome"
                        ] is not None
                        else None
                    ),
                )
            )

            if (
                current[
                    "control_duplicate_outcome"
                ]
                == "BUSINESS_DUPLICATE"
            ):
                guard_reasons = tuple(
                    dict.fromkeys(
                        (
                            *guard_reasons,
                            "CONFIRMED_BUSINESS_DUPLICATE",
                        )
                    )
                )

            if guard_reasons:
                raise ReviewCaseConflictError(
                    "Manual approval is blocked: "
                    + ", ".join(
                        guard_reasons
                    )
                )

            case_status = (
                "RESOLVED_APPROVED"
            )

            document_status = (
                "AUTO_APPROVED"
            )

            event_type = (
                "RESOLVED_APPROVED"
            )

            message = (
                "The review case was manually approved "
                "after corrected controls passed."
            )

        else:
            case_status = (
                "RESOLVED_REJECTED"
            )

            document_status = (
                "REJECTED"
            )

            event_type = (
                "RESOLVED_REJECTED"
            )

            message = (
                "The review case was manually rejected."
            )

        case_result = await connection.execute(
            update_case,
            {
                "case_status": case_status,
                "actor_user_id": actor.user_id,
                "actor_email": actor.email,
                "resolution_note": (
                    normalized_note
                ),
                "review_case_id": (
                    review_case_id
                ),
            },
        )

        resolved_case = dict(
            case_result
            .mappings()
            .one()
        )

        document_result = await connection.execute(
            update_document,
            {
                "document_status": (
                    document_status
                ),
                "resolution_note": (
                    normalized_note
                ),
                "actor_user_id": actor.user_id,
                "actor_email": actor.email,
                "document_id": str(
                    current["document_id"]
                ),
            },
        )

        resolved_document = dict(
            document_result
            .mappings()
            .one()
        )

        await connection.execute(
            insert_event,
            {
                "review_case_id": (
                    review_case_id
                ),
                "document_id": str(
                    current["document_id"]
                ),
                "actor_user_id": actor.user_id,
                "actor_email": actor.email,
                "actor_role": actor.role,
                "event_type": event_type,
                "message": message,
                "metadata": json.dumps(
                    {
                        "resolution": (
                            normalized_resolution
                        ),
                        "resolution_note": (
                            normalized_note
                        ),
                        "control_run_id": (
                            str(
                                current[
                                    "latest_control_run_id"
                                ]
                            )
                            if current[
                                "latest_control_run_id"
                            ] is not None
                            else None
                        ),
                        "control_outcome": (
                            current[
                                "control_outcome"
                            ]
                        ),
                        "guard_reasons": list(
                            guard_reasons
                        ),
                        "previous_document_status": (
                            current[
                                "document_status"
                            ]
                        ),
                        "final_document_status": (
                            document_status
                        ),
                    }
                ),
            },
        )

    return {
        "review_case": _json_safe(
            resolved_case
        ),
        "document": _json_safe(
            resolved_document
        ),
    }


def _json_safe(
    value: Any,
) -> Any:
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

    if hasattr(
        value,
        "isoformat",
    ):
        return value.isoformat()

    return str(value) if hasattr(
        value,
        "hex",
    ) else value