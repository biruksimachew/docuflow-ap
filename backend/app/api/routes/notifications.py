from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.responses import (
    JSONResponse,
)
from pydantic import (
    BaseModel,
    Field,
)

from app.core.config import settings
from app.security.dependencies import (
    require_roles,
)
from app.security.models import (
    AuthenticatedUser,
)
from app.services.notifications.service import (
    NotificationConflictError,
    NotificationNotFoundError,
    create_notification_delivery,
    get_notification_snapshot,
    list_export_notifications,
    record_test_webhook_receipt,
    requeue_notification_delivery,
)
from app.workers.tasks import (
    deliver_notification_task,
)


router = APIRouter(
    tags=["Export Notifications"],
)


class CreateNotificationRequest(
    BaseModel
):
    channel: Literal[
        "WEBHOOK",
        "EMAIL",
    ]

    destination: str = Field(
        min_length=3,
        max_length=2000,
    )


@router.post(
    "/notifications/test-webhook/"
    "{mode}/{token}"
)
async def local_test_webhook(
    mode: Literal[
        "success",
        "fail-once",
    ],
    token: str,
    request: Request,
) -> JSONResponse:
    if settings.app_env != "local":
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail={
                "code": (
                    "TEST_WEBHOOK_DISABLED"
                ),
                "message": (
                    "The local test webhook is disabled."
                ),
            },
        )

    try:
        body = await request.json()
    except Exception:
        body = {}

    receipt = (
        await record_test_webhook_receipt(
            token=token,
            mode=mode,
            request_headers={
                key: value
                for key, value
                in request.headers.items()
            },
            request_body=body,
        )
    )

    response_status = receipt[
        "response_status"
    ]

    return JSONResponse(
        status_code=response_status,
        content={
            "received": (
                response_status == 200
            ),
            "mode": mode,
            "token": token,
            "attempt_number": (
                receipt[
                    "attempt_number"
                ]
            ),
        },
    )


@router.post(
    "/exports/{export_id}/notifications"
)
async def create_export_notification(
    export_id: UUID,
    request: CreateNotificationRequest,
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "AP_CLERK",
            "REVIEWER",
            "ADMIN",
        )
    ),
) -> dict:
    try:
        result = await create_notification_delivery(
            export_id=str(
                export_id
            ),
            channel=request.channel,
            destination=request.destination,
            actor=current_user,
        )
    except NotificationNotFoundError as exc:
        raise _not_found() from exc
    except NotificationConflictError as exc:
        raise _conflict(
            str(exc)
        ) from exc
    except ValueError as exc:
        raise _unprocessable(
            str(exc)
        ) from exc

    if result["should_enqueue"]:
        deliver_notification_task.delay(
            result["delivery"]["id"]
        )

    return {
        "status": (
            "reused"
            if result[
                "idempotent_reuse"
            ]
            else "queued"
        ),
        "delivery": result[
            "delivery"
        ],
        "idempotent_reuse": result[
            "idempotent_reuse"
        ],
    }


@router.get(
    "/exports/{export_id}/notifications"
)
async def export_notifications(
    export_id: UUID,
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "AP_CLERK",
            "REVIEWER",
            "ADMIN",
        )
    ),
) -> dict:
    deliveries = await list_export_notifications(
        str(export_id)
    )

    return {
        "requested_by": {
            "user_id": (
                current_user.user_id
            ),
            "role": (
                current_user.role
            ),
        },
        "count": len(
            deliveries
        ),
        "deliveries": deliveries,
    }


@router.get(
    "/notifications/{delivery_id}"
)
async def notification_detail(
    delivery_id: UUID,
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "AP_CLERK",
            "REVIEWER",
            "ADMIN",
        )
    ),
) -> dict:
    try:
        snapshot = await get_notification_snapshot(
            str(delivery_id)
        )
    except NotificationNotFoundError as exc:
        raise _not_found() from exc

    snapshot["requested_by"] = {
        "user_id": current_user.user_id,
        "role": current_user.role,
    }

    return snapshot


@router.post(
    "/notifications/{delivery_id}/retry"
)
async def retry_notification(
    delivery_id: UUID,
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "ADMIN",
        )
    ),
) -> dict:
    try:
        delivery = (
            await requeue_notification_delivery(
                str(delivery_id)
            )
        )
    except NotificationNotFoundError as exc:
        raise _not_found() from exc
    except NotificationConflictError as exc:
        raise _conflict(
            str(exc)
        ) from exc

    deliver_notification_task.delay(
        delivery["id"]
    )

    return {
        "status": "requeued",
        "delivery": delivery,
        "requested_by": {
            "user_id": (
                current_user.user_id
            ),
            "role": (
                current_user.role
            ),
        },
    }


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=(
            status.HTTP_404_NOT_FOUND
        ),
        detail={
            "code": (
                "NOTIFICATION_NOT_FOUND"
            ),
            "message": (
                "The export or notification does not exist."
            ),
        },
    )


def _conflict(
    message: str,
) -> HTTPException:
    return HTTPException(
        status_code=(
            status.HTTP_409_CONFLICT
        ),
        detail={
            "code": (
                "NOTIFICATION_CONFLICT"
            ),
            "message": message,
        },
    )


def _unprocessable(
    message: str,
) -> HTTPException:
    return HTTPException(
        status_code=(
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ),
        detail={
            "code": (
                "INVALID_NOTIFICATION_DESTINATION"
            ),
            "message": message,
        },
    )
