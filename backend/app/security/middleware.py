from __future__ import annotations

import os

from fastapi import Request
from starlette.middleware.base import (
    BaseHTTPMiddleware,
)
from starlette.responses import (
    JSONResponse,
)

from app.security.errors import (
    AuthenticationError,
)
from app.security.service import (
    authenticate_request,
)


class DocumentSecurityMiddleware(
    BaseHTTPMiddleware
):
    """
    Require authentication for document evidence endpoints.

    The upload endpoint remains available to approved intake integrations.
    """

    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        if (
            _enforcement_enabled()
            and _is_protected_document_path(
                request
            )
        ):
            try:
                await authenticate_request(
                    request
                )
            except AuthenticationError as exc:
                return JSONResponse(
                    status_code=exc.status_code,
                    content={
                        "detail": {
                            "code": exc.code,
                            "message": (
                                exc.message
                            ),
                        }
                    },
                    headers={
                        "WWW-Authenticate": (
                            "Bearer"
                        ),
                    },
                )

        return await call_next(
            request
        )


def _enforcement_enabled() -> bool:
    return os.getenv(
        "AUTH_ENFORCEMENT_ENABLED",
        "true",
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _is_protected_document_path(
    request: Request,
) -> bool:
    path = request.url.path.rstrip(
        "/"
    )

    if not path.startswith(
        "/api/v1/documents/"
    ):
        return False

    if (
        request.method.upper() == "POST"
        and path
        == "/api/v1/documents/upload"
    ):
        return False

    return True