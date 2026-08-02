from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)
from pydantic import BaseModel

from app.security.dependencies import (
    require_roles,
)
from app.security.models import (
    AuthenticatedUser,
)
from app.services.accounting_exports.service import (
    AccountingExportConflictError,
    AccountingExportNotFoundError,
    download_accounting_export,
    generate_accounting_export,
    get_export_snapshot,
    list_document_exports,
)


router = APIRouter(
    tags=["Accounting Exports"],
)


class CreateAccountingExportRequest(
    BaseModel
):
    export_format: Literal[
        "JSON",
        "CSV",
    ]


@router.post(
    "/documents/{document_id}/exports"
)
async def create_accounting_export(
    document_id: UUID,
    request: CreateAccountingExportRequest,
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "AP_CLERK",
            "REVIEWER",
            "ADMIN",
        )
    ),
) -> dict:
    try:
        result = await generate_accounting_export(
            document_id=str(
                document_id
            ),
            export_format=(
                request.export_format
            ),
            actor=current_user,
        )
    except AccountingExportNotFoundError as exc:
        raise _not_found() from exc
    except AccountingExportConflictError as exc:
        raise _conflict(
            str(exc)
        ) from exc

    return {
        "status": (
            "reused"
            if result["idempotent_reuse"]
            else "generated"
        ),
        **result,
    }


@router.get(
    "/documents/{document_id}/exports"
)
async def document_accounting_exports(
    document_id: UUID,
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "AP_CLERK",
            "REVIEWER",
            "ADMIN",
        )
    ),
) -> dict:
    exports = await list_document_exports(
        str(document_id)
    )

    return {
        "requested_by": {
            "user_id": current_user.user_id,
            "role": current_user.role,
        },
        "count": len(exports),
        "exports": exports,
    }


@router.get(
    "/exports/{export_id}"
)
async def accounting_export_detail(
    export_id: UUID,
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "AP_CLERK",
            "REVIEWER",
            "ADMIN",
        )
    ),
) -> dict:
    try:
        snapshot = await get_export_snapshot(
            str(export_id)
        )
    except AccountingExportNotFoundError as exc:
        raise _not_found() from exc

    snapshot["requested_by"] = {
        "user_id": current_user.user_id,
        "role": current_user.role,
    }

    return snapshot


@router.get(
    "/exports/{export_id}/download"
)
async def download_export(
    export_id: UUID,
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "AP_CLERK",
            "REVIEWER",
            "ADMIN",
        )
    ),
) -> Response:
    try:
        export_record = (
            await download_accounting_export(
                export_id=str(
                    export_id
                ),
                actor=current_user,
            )
        )
    except AccountingExportNotFoundError as exc:
        raise _not_found() from exc
    except AccountingExportConflictError as exc:
        raise _conflict(
            str(exc)
        ) from exc

    return Response(
        content=export_record[
            "payload_text"
        ],
        media_type=export_record[
            "content_type"
        ],
        headers={
            "Content-Disposition": (
                "attachment; filename="
                f'"{export_record["file_name"]}"'
            ),
            "X-Content-SHA256": (
                export_record[
                    "payload_sha256"
                ]
            ),
        },
    )


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": (
                "ACCOUNTING_EXPORT_NOT_FOUND"
            ),
            "message": (
                "The document or accounting export does not exist."
            ),
        },
    )


def _conflict(
    message: str,
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": (
                "ACCOUNTING_EXPORT_CONFLICT"
            ),
            "message": message,
        },
    )
