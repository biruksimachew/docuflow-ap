from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    status,
)

from app.services.validation.repository import (
    get_validation_snapshot,
)


router = APIRouter(
    prefix="/documents",
    tags=["Validation"],
)


@router.get(
    "/{document_id}/validation",
)
async def document_validation(
    document_id: UUID,
) -> dict:
    snapshot = await get_validation_snapshot(
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