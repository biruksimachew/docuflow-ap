from __future__ import annotations

from typing import Any, Literal
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
from app.services.reviews.control_service import (
    rerun_corrected_controls,
)
from app.services.reviews.correction_repository import (
    get_latest_review_control_run,
    list_review_corrections,
    load_effective_invoice,
)
from app.services.reviews.correction_service import (
    apply_correction,
    propose_correction,
    reject_correction,
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
from app.services.reviews.resolution_service import (
    resolve_review_case,
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


class CorrectionRequest(BaseModel):
    target_type: Literal[
        "HEADER",
        "LINE_ITEM",
    ]

    line_item_id: UUID | None = None

    field_name: str = Field(
        min_length=1,
        max_length=100,
    )

    corrected_value: Any = None

    reason: str = Field(
        min_length=5,
        max_length=1000,
    )

    apply_immediately: bool = False


class CorrectionRejectionRequest(
    BaseModel
):
    reason: str = Field(
        min_length=10,
        max_length=2000,
    )


class ResolutionRequest(BaseModel):
    resolution: Literal[
        "APPROVE",
        "REJECT",
    ]

    note: str = Field(
        min_length=10,
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

    corrections = await list_review_corrections(
        str(review_case_id)
    )

    control_run = await get_latest_review_control_run(
        str(review_case_id)
    )

    snapshot["corrections"] = (
        corrections
    )

    snapshot["latest_control_run"] = (
        control_run
    )

    snapshot["requested_by"] = {
        "user_id": current_user.user_id,
        "role": current_user.role,
    }

    return snapshot


@router.get(
    "/{review_case_id}/effective-invoice"
)
async def effective_invoice(
    review_case_id: UUID,
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
) -> dict:
    try:
        snapshot = await load_effective_invoice(
            str(review_case_id)
        )
    except ReviewCaseNotFoundError as exc:
        raise _not_found() from exc

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
        raise _not_found() from exc
    except ReviewCaseConflictError as exc:
        raise _conflict(
            str(exc)
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
        raise _not_found() from exc
    except ReviewCaseAuthorizationError as exc:
        raise _forbidden(
            str(exc)
        ) from exc
    except ReviewCaseConflictError as exc:
        raise _conflict(
            str(exc)
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
        raise _not_found() from exc
    except ReviewCaseConflictError as exc:
        raise _conflict(
            str(exc)
        ) from exc
    except ValueError as exc:
        raise _unprocessable(
            "INVALID_REVIEW_NOTE",
            str(exc),
        ) from exc

    return {
        "status": "note_added",
        "event": event,
    }


@router.post(
    "/{review_case_id}/corrections",
    status_code=status.HTTP_201_CREATED,
)
async def create_correction_endpoint(
    review_case_id: UUID,
    request: CorrectionRequest,
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
) -> dict:
    try:
        result = await propose_correction(
            review_case_id=str(
                review_case_id
            ),
            actor=current_user,
            target_type=(
                request.target_type
            ),
            line_item_id=(
                str(request.line_item_id)
                if request.line_item_id
                is not None
                else None
            ),
            field_name=(
                request.field_name
            ),
            corrected_value=(
                request.corrected_value
            ),
            reason=request.reason,
            apply_immediately=(
                request.apply_immediately
            ),
        )
    except ReviewCaseNotFoundError as exc:
        raise _not_found() from exc
    except ReviewCaseAuthorizationError as exc:
        raise _forbidden(
            str(exc)
        ) from exc
    except ReviewCaseConflictError as exc:
        raise _conflict(
            str(exc)
        ) from exc
    except PermissionError as exc:
        raise _forbidden(
            str(exc)
        ) from exc
    except ValueError as exc:
        raise _unprocessable(
            "INVALID_CORRECTION",
            str(exc),
        ) from exc

    return {
        "status": (
            result[
                "correction"
            ]["status"].lower()
        ),
        **result,
    }


@router.post(
    "/{review_case_id}/corrections/"
    "{correction_id}/apply"
)
async def apply_correction_endpoint(
    review_case_id: UUID,
    correction_id: UUID,
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "REVIEWER",
            "ADMIN",
        )
    ),
) -> dict:
    try:
        result = await apply_correction(
            review_case_id=str(
                review_case_id
            ),
            correction_id=str(
                correction_id
            ),
            actor=current_user,
        )
    except ReviewCaseNotFoundError as exc:
        raise _not_found() from exc
    except ReviewCaseAuthorizationError as exc:
        raise _forbidden(
            str(exc)
        ) from exc
    except ReviewCaseConflictError as exc:
        raise _conflict(
            str(exc)
        ) from exc

    return {
        "status": "applied",
        **result,
    }


@router.post(
    "/{review_case_id}/corrections/"
    "{correction_id}/reject"
)
async def reject_correction_endpoint(
    review_case_id: UUID,
    correction_id: UUID,
    request: CorrectionRejectionRequest,
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "REVIEWER",
            "ADMIN",
        )
    ),
) -> dict:
    try:
        correction = await reject_correction(
            review_case_id=str(
                review_case_id
            ),
            correction_id=str(
                correction_id
            ),
            actor=current_user,
            rejection_reason=(
                request.reason
            ),
        )
    except ReviewCaseNotFoundError as exc:
        raise _not_found() from exc
    except ReviewCaseAuthorizationError as exc:
        raise _forbidden(
            str(exc)
        ) from exc
    except ReviewCaseConflictError as exc:
        raise _conflict(
            str(exc)
        ) from exc
    except ValueError as exc:
        raise _unprocessable(
            "INVALID_REJECTION_REASON",
            str(exc),
        ) from exc

    return {
        "status": "rejected",
        "correction": correction,
    }


@router.post(
    "/{review_case_id}/rerun"
)
async def rerun_controls_endpoint(
    review_case_id: UUID,
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "REVIEWER",
            "ADMIN",
        )
    ),
) -> dict:
    try:
        control_run = (
            await rerun_corrected_controls(
                review_case_id=str(
                    review_case_id
                ),
                actor=current_user,
            )
        )
    except ReviewCaseNotFoundError as exc:
        raise _not_found() from exc

    return {
        "status": "completed",
        "control_run": control_run,
    }


@router.post(
    "/{review_case_id}/resolve"
)
async def resolve_review_case_endpoint(
    review_case_id: UUID,
    request: ResolutionRequest,
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "REVIEWER",
            "ADMIN",
        )
    ),
) -> dict:
    try:
        result = await resolve_review_case(
            review_case_id=str(
                review_case_id
            ),
            actor=current_user,
            resolution=(
                request.resolution
            ),
            note=request.note,
        )
    except ReviewCaseNotFoundError as exc:
        raise _not_found() from exc
    except ReviewCaseAuthorizationError as exc:
        raise _forbidden(
            str(exc)
        ) from exc
    except ReviewCaseConflictError as exc:
        raise _conflict(
            str(exc)
        ) from exc
    except ValueError as exc:
        raise _unprocessable(
            "INVALID_RESOLUTION",
            str(exc),
        ) from exc

    return {
        "status": "resolved",
        "resolution": (
            request.resolution
        ),
        **result,
    }


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "REVIEW_CASE_NOT_FOUND",
            "message": (
                "The review case or correction does not exist."
            ),
        },
    )


def _forbidden(
    message: str,
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "REVIEW_ACTION_DENIED",
            "message": message,
        },
    )


def _conflict(
    message: str,
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "REVIEW_CASE_CONFLICT",
            "message": message,
        },
    )


def _unprocessable(
    code: str,
    message: str,
) -> HTTPException:
    return HTTPException(
        status_code=(
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ),
        detail={
            "code": code,
            "message": message,
        },
    )