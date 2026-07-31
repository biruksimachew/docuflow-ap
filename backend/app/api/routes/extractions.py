from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    status,
)

from app.services.extraction.repository import (
    get_extraction_snapshot,
)


router = APIRouter(
    prefix="/documents",
    tags=["Extraction"],
)


@router.get(
    "/{document_id}/extraction",
)
async def document_extraction(
    document_id: UUID,
) -> dict:
    snapshot = await get_extraction_snapshot(
        str(document_id)
    )

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "DOCUMENT_NOT_FOUND",
                "message": "The document does not exist.",
            },
        )

    return snapshot