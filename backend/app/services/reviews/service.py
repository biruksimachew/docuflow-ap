from __future__ import annotations

from typing import Any

from app.security.models import AuthenticatedUser
from app.services.reviews.policy import (
    normalize_review_note,
)
from app.services.reviews.repository import (
    add_review_note,
    claim_review_case,
    ensure_review_case,
    release_review_case,
)


async def ensure_review_case_for_decision(
    *,
    document_id: str,
    decision_run_id: str,
    reason_codes: list[str],
    explanation: str,
) -> dict[str, Any]:
    return await ensure_review_case(
        document_id=document_id,
        decision_run_id=decision_run_id,
        reason_codes=reason_codes,
        explanation=explanation,
    )


async def claim_case(
    *,
    review_case_id: str,
    actor: AuthenticatedUser,
) -> dict[str, Any]:
    return await claim_review_case(
        review_case_id=review_case_id,
        actor=actor,
    )


async def release_case(
    *,
    review_case_id: str,
    actor: AuthenticatedUser,
) -> dict[str, Any]:
    return await release_review_case(
        review_case_id=review_case_id,
        actor=actor,
    )


async def add_note(
    *,
    review_case_id: str,
    actor: AuthenticatedUser,
    note: str,
) -> dict[str, Any]:
    normalized_note = normalize_review_note(
        note
    )

    return await add_review_note(
        review_case_id=review_case_id,
        actor=actor,
        note=normalized_note,
    )