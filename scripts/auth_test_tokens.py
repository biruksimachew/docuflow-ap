from __future__ import annotations

import os
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from typing import Any

import httpx
import jwt


TEST_USERS = {
    "AP_CLERK": {
        "sub": (
            "90000000-0000-0000-0000-000000000001"
        ),
        "email": (
            "clerk@docuflow.local"
        ),
    },
    "REVIEWER": {
        "sub": (
            "90000000-0000-0000-0000-000000000002"
        ),
        "email": (
            "reviewer@docuflow.local"
        ),
    },
    "ADMIN": {
        "sub": (
            "90000000-0000-0000-0000-000000000003"
        ),
        "email": (
            "admin@docuflow.local"
        ),
    },
}


def create_test_access_token(
    *,
    role: str,
    expires_in_seconds: int = 3600,
    secret: str | None = None,
    audience: str | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    user = TEST_USERS[
        role
    ]

    now = datetime.now(
        timezone.utc
    )

    claims: dict[str, Any] = {
        "sub": user["sub"],
        "email": user["email"],
        "aud": (
            audience
            or os.getenv(
                "AUTH_JWT_AUDIENCE",
                "authenticated",
            )
        ),
        "role": "authenticated",
        "iat": int(
            now.timestamp()
        ),
        "exp": int(
            (
                now
                + timedelta(
                    seconds=(
                        expires_in_seconds
                    )
                )
            ).timestamp()
        ),
    }

    if extra_claims:
        claims.update(
            extra_claims
        )

    return jwt.encode(
        claims,
        (
            secret
            or os.getenv(
                "SUPABASE_JWT_SECRET",
                "",
            )
        ),
        algorithm=os.getenv(
            "AUTH_JWT_ALGORITHM",
            "HS256",
        ),
    )


def authorization_headers(
    role: str = "ADMIN",
) -> dict[str, str]:
    return {
        "Authorization": (
            "Bearer "
            + create_test_access_token(
                role=role
            )
        )
    }


def authenticated_get(
    url: str,
    *,
    role: str = "ADMIN",
    headers: dict[str, str] | None = None,
    **kwargs,
) -> httpx.Response:
    merged_headers = authorization_headers(
        role
    )

    if headers:
        merged_headers.update(
            headers
        )

    return httpx.get(
        url,
        headers=merged_headers,
        **kwargs,
    )