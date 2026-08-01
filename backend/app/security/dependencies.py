from __future__ import annotations

from collections.abc import Callable

from fastapi import (
    Depends,
    HTTPException,
    Request,
    status,
)

from app.security.errors import (
    AuthenticationError,
)
from app.security.models import (
    AuthenticatedUser,
    role_allowed,
)
from app.security.service import (
    audit_authorization_denied,
    authenticate_request,
)


async def get_current_user(
    request: Request,
) -> AuthenticatedUser:
    existing = getattr(
        request.state,
        "current_user",
        None,
    )

    if existing is not None:
        return existing

    try:
        return await authenticate_request(
            request
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": exc.code,
                "message": exc.message,
            },
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from exc


def require_roles(
    *roles: str,
) -> Callable:
    allowed_roles = set(
        roles
    )

    async def dependency(
        request: Request,
        current_user: AuthenticatedUser = Depends(
            get_current_user
        ),
    ) -> AuthenticatedUser:
        if role_allowed(
            current_user.role,
            allowed_roles,
        ):
            return current_user

        await audit_authorization_denied(
            request=request,
            user=current_user,
            required_roles=allowed_roles,
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "INSUFFICIENT_ROLE",
                "message": (
                    "The authenticated user does not "
                    "have permission for this operation."
                ),
                "required_roles": sorted(
                    allowed_roles
                ),
                "actual_role": (
                    current_user.role
                ),
            },
        )

    return dependency