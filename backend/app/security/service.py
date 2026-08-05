from __future__ import annotations

from uuid import uuid4

from fastapi import Request
from starlette.concurrency import (
    run_in_threadpool,
)

from app.security.errors import (
    AuthenticationError,
)
from app.security.jwt import (
    decode_supabase_access_token,
)
from app.security.models import (
    AuthenticatedUser,
)
from app.security.repository import (
    create_security_audit_event,
    get_active_role_assignment,
)


async def authenticate_request(
    request: Request,
) -> AuthenticatedUser:
    """Authenticate a bearer token and resolve its application role."""

    request_id = _request_id(
        request
    )

    authorization = request.headers.get(
        "Authorization",
        "",
    ).strip()

    if not authorization:
        await _safe_audit(
            request=request,
            request_id=request_id,
            event_type="AUTHENTICATION_FAILED",
            status_code=401,
            reason=(
                "The protected endpoint was called "
                "without a bearer token."
            ),
            metadata={
                "code": "MISSING_ACCESS_TOKEN",
            },
        )

        raise AuthenticationError(
            code="MISSING_ACCESS_TOKEN",
            message=(
                "A bearer access token is required."
            ),
        )

    scheme, separator, token = (
        authorization.partition(
            " "
        )
    )

    if (
        not separator
        or scheme.lower() != "bearer"
        or not token.strip()
    ):
        await _safe_audit(
            request=request,
            request_id=request_id,
            event_type="AUTHENTICATION_FAILED",
            status_code=401,
            reason=(
                "The Authorization header did not use "
                "the Bearer scheme."
            ),
            metadata={
                "code": "INVALID_AUTHORIZATION_HEADER",
            },
        )

        raise AuthenticationError(
            code="INVALID_AUTHORIZATION_HEADER",
            message=(
                "Authorization must use the Bearer scheme."
            ),
        )

    try:
        decoded = await run_in_threadpool(
            decode_supabase_access_token,
            token.strip(),
        )
    except AuthenticationError as exc:
        await _safe_audit(
            request=request,
            request_id=request_id,
            event_type="AUTHENTICATION_FAILED",
            status_code=401,
            reason=exc.message,
            metadata={
                "code": exc.code,
            },
        )

        raise

    role_assignment = (
        await get_active_role_assignment(
            decoded.subject
        )
    )

    if role_assignment is None:
        await _safe_audit(
            request=request,
            request_id=request_id,
            user_id=decoded.subject,
            email=decoded.email,
            event_type="AUTHENTICATION_FAILED",
            status_code=401,
            reason=(
                "The authenticated Supabase user has no "
                "active DocuFlow role assignment."
            ),
            metadata={
                "code": "USER_NOT_PROVISIONED",
                "token_role": (
                    decoded.token_role
                ),
            },
        )

        raise AuthenticationError(
            code="USER_NOT_PROVISIONED",
            message=(
                "The authenticated user is not provisioned "
                "for DocuFlow AP."
            ),
        )

    user = AuthenticatedUser(
        user_id=str(
            role_assignment[
                "user_id"
            ]
        ),
        email=str(
            role_assignment[
                "email"
            ]
        ),
        display_name=str(
            role_assignment[
                "display_name"
            ]
        ),
        role=str(
            role_assignment[
                "role"
            ]
        ),
        token_role=(
            decoded.token_role
        ),
        token_expires_at=(
            decoded.expires_at
        ),
    )

    request.state.current_user = user

    await _safe_audit(
        request=request,
        request_id=request_id,
        user_id=user.user_id,
        email=user.email,
        app_role=user.role,
        event_type="AUTHENTICATION_SUCCEEDED",
        status_code=200,
        reason=(
            "The bearer token and application role "
            "were validated."
        ),
        metadata={
            "token_role": user.token_role,
            "token_expires_at": (
                user.token_expires_at
            ),
        },
    )

    return user


async def audit_authorization_denied(
    *,
    request: Request,
    user: AuthenticatedUser,
    required_roles: set[str],
) -> None:
    await _safe_audit(
        request=request,
        request_id=_request_id(
            request
        ),
        user_id=user.user_id,
        email=user.email,
        app_role=user.role,
        event_type="AUTHORIZATION_DENIED",
        status_code=403,
        reason=(
            "The authenticated application role is not "
            "authorized for this endpoint."
        ),
        metadata={
            "required_roles": sorted(
                required_roles
            ),
            "actual_role": user.role,
        },
    )


def _request_id(
    request: Request,
) -> str:
    existing = getattr(
        request.state,
        "security_request_id",
        None,
    )

    if existing:
        return str(
            existing
        )

    request_id = str(
        uuid4()
    )

    request.state.security_request_id = (
        request_id
    )

    return request_id


async def _safe_audit(
    *,
    request: Request,
    request_id: str,
    event_type: str,
    status_code: int,
    reason: str,
    metadata: dict,
    user_id: str | None = None,
    email: str | None = None,
    app_role: str | None = None,
) -> None:
    try:
        await create_security_audit_event(
            request_id=request_id,
            user_id=user_id,
            email=email,
            app_role=app_role,
            event_type=event_type,
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            reason=reason,
            metadata=metadata,
        )
    except Exception:
        # Authentication must not expose internal audit-storage errors.
        pass