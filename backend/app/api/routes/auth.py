from fastapi import (
    APIRouter,
    Depends,
    Query,
)

from app.security.dependencies import (
    get_current_user,
    require_roles,
)
from app.security.models import (
    AuthenticatedUser,
)
from app.security.repository import (
    list_security_audit_events,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication and RBAC"],
)


@router.get(
    "/me",
)
async def current_user_profile(
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
) -> dict:
    return {
        "authenticated": True,
        "user": {
            "user_id": (
                current_user.user_id
            ),
            "email": (
                current_user.email
            ),
            "display_name": (
                current_user.display_name
            ),
            "role": (
                current_user.role
            ),
            "token_role": (
                current_user.token_role
            ),
            "token_expires_at": (
                current_user.token_expires_at
            ),
        },
    }


@router.get(
    "/reviewer-check",
)
async def reviewer_access_check(
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "REVIEWER",
            "ADMIN",
        )
    ),
) -> dict:
    return {
        "authorized": True,
        "capability": (
            "HUMAN_REVIEW"
        ),
        "role": current_user.role,
    }


@router.get(
    "/admin-check",
)
async def admin_access_check(
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "ADMIN",
        )
    ),
) -> dict:
    return {
        "authorized": True,
        "capability": (
            "SYSTEM_ADMINISTRATION"
        ),
        "role": current_user.role,
    }


@router.get(
    "/security-events",
)
async def security_events(
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    current_user: AuthenticatedUser = Depends(
        require_roles(
            "ADMIN",
        )
    ),
) -> dict:
    events = await list_security_audit_events(
        limit=limit
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
            events
        ),
        "events": events,
    }