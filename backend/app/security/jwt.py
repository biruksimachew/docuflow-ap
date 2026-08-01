from __future__ import annotations

import os
from uuid import UUID

import jwt
from jwt import PyJWTError

from app.security.errors import (
    AuthenticationError,
)
from app.security.models import (
    DecodedSupabaseToken,
)


def decode_supabase_access_token(
    token: str,
) -> DecodedSupabaseToken:
    """
    Validate a Supabase-compatible authenticated-user JWT.

    Signature, algorithm, audience, subject and expiration are enforced.
    Application authorization is loaded separately from the database.
    """

    secret = os.getenv(
        "SUPABASE_JWT_SECRET",
        "",
    ).strip()

    algorithm = os.getenv(
        "AUTH_JWT_ALGORITHM",
        "HS256",
    ).strip()

    audience = os.getenv(
        "AUTH_JWT_AUDIENCE",
        "authenticated",
    ).strip()

    if not secret:
        raise RuntimeError(
            "SUPABASE_JWT_SECRET is required."
        )

    if algorithm != "HS256":
        raise RuntimeError(
            "Only HS256 Supabase JWT validation is "
            "enabled for this deployment."
        )

    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[
                algorithm,
            ],
            audience=audience,
            options={
                "require": [
                    "sub",
                    "aud",
                    "exp",
                ],
            },
        )
    except PyJWTError as exc:
        raise AuthenticationError(
            code="INVALID_ACCESS_TOKEN",
            message=(
                "The access token is invalid, expired "
                "or was issued for another audience."
            ),
        ) from exc

    subject = str(
        claims.get(
            "sub",
            "",
        )
    ).strip()

    try:
        UUID(
            subject
        )
    except ValueError as exc:
        raise AuthenticationError(
            code="INVALID_TOKEN_SUBJECT",
            message=(
                "The access token subject is not a "
                "valid user identifier."
            ),
        ) from exc

    token_role = str(
        claims.get(
            "role",
            "",
        )
    ).strip()

    if token_role != "authenticated":
        raise AuthenticationError(
            code="INVALID_TOKEN_ROLE",
            message=(
                "Only authenticated end-user tokens "
                "can access this API."
            ),
        )

    expires_at = claims.get(
        "exp"
    )

    if not isinstance(
        expires_at,
        int,
    ):
        raise AuthenticationError(
            code="INVALID_TOKEN_EXPIRATION",
            message=(
                "The access token does not contain a "
                "valid expiration timestamp."
            ),
        )

    issued_at = claims.get(
        "iat"
    )

    return DecodedSupabaseToken(
        subject=subject,
        email=(
            str(claims["email"]).strip()
            if claims.get("email")
            else None
        ),
        token_role=token_role,
        issued_at=(
            int(issued_at)
            if isinstance(
                issued_at,
                int,
            )
            else None
        ),
        expires_at=expires_at,
        claims=dict(
            claims
        ),
    )