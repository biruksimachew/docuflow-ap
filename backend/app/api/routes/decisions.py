from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    status,
)

from app.services.decisions.repository import (
    get_decision_snapshot,
)


router = APIRouter(
    prefix="/documents",
    tags=["Invoice Decisions"],
)


@router.get(
    "/{document_id}/decision",
)
async def document_decision(
    document_id: UUID,
) -> dict:
    snapshot = await get_decision_snapshot(
        str(document_id)
    )

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "DOCUMENT_NOT_FOUND",
                "message": (
                    "The document does not exist."
                ),
            },
        )

    return snapshot