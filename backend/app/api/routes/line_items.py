from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    status,
)

from app.services.line_items.repository import (
    get_line_item_snapshot,
)


router = APIRouter(
    prefix="/documents",
    tags=["Line Items"],
)


@router.get(
    "/{document_id}/line-items",
)
async def document_line_items(
    document_id: UUID,
) -> dict:
    snapshot = await get_line_item_snapshot(
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