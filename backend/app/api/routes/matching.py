from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    status,
)

from app.services.matching.repository import (
    get_matching_snapshot,
)


router = APIRouter(
    prefix="/documents",
    tags=["Vendor and PO Matching"],
)


@router.get(
    "/{document_id}/matching",
)
async def document_matching(
    document_id: UUID,
) -> dict:
    snapshot = await get_matching_snapshot(
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