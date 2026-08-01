from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from pydantic import (
    BaseModel,
    Field,
)

from app.security.dependencies import (
    get_current_user,
    require_roles,
)
from app.security.models import (
    AuthenticatedUser,
)
from app.services.reviews.errors import (
    ReviewCaseAuthorizationError,
    ReviewCaseConflictError,
    ReviewCaseNotFoundError,
)
from app.services.reviews.repository import (
    get_review_case_snapshot,
    list_review_cases,
)
from app.services.reviews.service import (
    add_note,
    claim_case,
    release_case,
)


router = APIRouter(
    prefix="/reviews",
    tags=["Human Review"],
)


class ReviewNoteRequest(BaseModel):
    note: str = Field(
        min_length=1,
        max_length=2000,
    )


@router.get("")
async def review_queue(
    review_status: Literal[
        "OPEN",
        "CLAIMED",
        "RESOLVED_APPROVED",
        "RESOLVED_REJECTED",
        "CANCELLED",
    ] | None = Query(
        default=None,
        alias="status",
    ),
    document_id: UUID | None = Query(
        default=None
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
) -> dict:
    cases = await list_review_cases(
        status=review_status,
        document_id=(
            str(document_id)
            if document_id is not None
            else None
        ),
        limit=limit,
    )

    return {
        "requested_by": {
            "user_id": current_user.user_id,
            "role": current_user.role,
        },
        "count": len(cases),
        "cases": cases,
    }


@router.get("/{review_case_id}")
async def review_case_detail(
    review_case_id: UUID,
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
) -> dict:
    snapshot = await get_review_case_snapshot(
        str(review_case_id)
    )

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "REVIEW_CASE_NOT_FOUND",
                "message": (
                    "The review case does not exist."
                ),
            },
        )

    snapshot["requested_by"] = {
        "user_id": current_user.user_id,
        "role": current_user.role,
    }

    return snapshot


@router.post("/{review_case_id}/claim")
async def claim_review_case_endpoint(
    review_case_id: UUID,
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "REVIEWER",
            "ADMIN",
        )
    ),
) -> dict:
    try:
        review_case = await claim_case(
            review_case_id=str(
                review_case_id
            ),
            actor=current_user,
        )
    except ReviewCaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "REVIEW_CASE_NOT_FOUND",
                "message": (
                    "The review case does not exist."
                ),
            },
        ) from exc
    except ReviewCaseConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REVIEW_CASE_CONFLICT",
                "message": str(exc),
            },
        ) from exc

    return {
        "status": "claimed",
        "review_case": review_case,
    }


@router.post("/{review_case_id}/release")
async def release_review_case_endpoint(
    review_case_id: UUID,
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "REVIEWER",
            "ADMIN",
        )
    ),
) -> dict:
    try:
        review_case = await release_case(
            review_case_id=str(
                review_case_id
            ),
            actor=current_user,
        )
    except ReviewCaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "REVIEW_CASE_NOT_FOUND",
                "message": (
                    "The review case does not exist."
                ),
            },
        ) from exc
    except ReviewCaseAuthorizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "REVIEW_CASE_RELEASE_DENIED",
                "message": str(exc),
            },
        ) from exc
    except ReviewCaseConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REVIEW_CASE_CONFLICT",
                "message": str(exc),
            },
        ) from exc

    return {
        "status": "released",
        "review_case": review_case,
    }


@router.post("/{review_case_id}/notes")
async def add_review_note_endpoint(
    review_case_id: UUID,
    request: ReviewNoteRequest,
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
) -> dict:
    try:
        event = await add_note(
            review_case_id=str(
                review_case_id
            ),
            actor=current_user,
            note=request.note,
        )
    except ReviewCaseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "REVIEW_CASE_NOT_FOUND",
                "message": (
                    "The review case does not exist."
                ),
            },
        ) from exc
    except ReviewCaseConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REVIEW_CASE_CONFLICT",
                "message": str(exc),
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_REVIEW_NOTE",
                "message": str(exc),
            },
        ) from exc

    return {
        "status": "note_added",
        "event": event,
    }