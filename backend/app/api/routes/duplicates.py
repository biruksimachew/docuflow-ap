from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    status,
)

from app.services.duplicates.repository import (
    get_duplicate_snapshot,
)


router = APIRouter(
    prefix="/documents",
    tags=["Business Duplicates"],
)


@router.get(
    "/{document_id}/duplicate-check",
)
async def document_duplicate_check(
    document_id: UUID,
) -> dict:
    snapshot = await get_duplicate_snapshot(
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