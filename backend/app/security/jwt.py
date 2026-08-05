from __future__ import annotations

import os
from functools import lru_cache
from uuid import UUID

import jwt
from jwt import (
    PyJWKClient,
    PyJWKClientError,
    PyJWTError,
)

from app.security.errors import (
    AuthenticationError,
)
from app.security.models import (
    DecodedSupabaseToken,
)


SUPPORTED_JWT_ALGORITHMS = frozenset(
    {
        "HS256",
        "ES256",
        "RS256",
    }
)

ASYMMETRIC_JWT_ALGORITHMS = frozenset(
    {
        "ES256",
        "RS256",
    }
)


def _authentication_error(
    *,
    code: str = "INVALID_ACCESS_TOKEN",
    message: str = (
        "The access token is invalid, expired "
        "or was issued for another audience."
    ),
) -> AuthenticationError:
    return AuthenticationError(
        code=code,
        message=message,
    )


def _allowed_algorithms() -> frozenset[str]:
    configured = os.getenv(
        "AUTH_JWT_ALGORITHMS",
        "HS256,ES256",
    )

    algorithms = frozenset(
        value.strip().upper()
        for value in configured.split(",")
        if value.strip()
    )

    unsupported = (
        algorithms
        - SUPPORTED_JWT_ALGORITHMS
    )

    if unsupported:
        raise RuntimeError(
            "AUTH_JWT_ALGORITHMS contains unsupported "
            "algorithms: "
            + ", ".join(
                sorted(unsupported)
            )
        )

    if not algorithms:
        raise RuntimeError(
            "AUTH_JWT_ALGORITHMS must enable at least "
            "one supported JWT algorithm."
        )

    return algorithms


def _supabase_jwks_url() -> str:
    configured = os.getenv(
        "SUPABASE_JWKS_URL",
        "",
    ).strip()

    if configured:
        return configured

    supabase_url = os.getenv(
        "SUPABASE_URL",
        "",
    ).strip().rstrip("/")

    if not supabase_url:
        raise RuntimeError(
            "SUPABASE_URL or SUPABASE_JWKS_URL is "
            "required for asymmetric JWT validation."
        )

    if supabase_url.endswith(
        "/auth/v1"
    ):
        return (
            f"{supabase_url}"
            "/.well-known/jwks.json"
        )

    return (
        f"{supabase_url}"
        "/auth/v1/.well-known/jwks.json"
    )


@lru_cache(
    maxsize=8
)
def _jwks_client(
    jwks_url: str,
) -> PyJWKClient:
    return PyJWKClient(
        jwks_url
    )


def _verification_key(
    token: str,
) -> tuple[object, str]:
    try:
        header = jwt.get_unverified_header(
            token
        )
    except PyJWTError as exc:
        raise _authentication_error() from exc

    algorithm = str(
        header.get(
            "alg",
            "",
        )
    ).strip().upper()

    if (
        not algorithm
        or algorithm not in _allowed_algorithms()
    ):
        raise _authentication_error(
            code="UNSUPPORTED_TOKEN_ALGORITHM",
            message=(
                "The access token uses an unsupported "
                "signing algorithm."
            ),
        )

    if algorithm == "HS256":
        secret = os.getenv(
            "SUPABASE_JWT_SECRET",
            "",
        ).strip()

        if not secret:
            raise RuntimeError(
                "SUPABASE_JWT_SECRET is required for "
                "HS256 JWT validation."
            )

        return secret, algorithm

    if (
        algorithm
        in ASYMMETRIC_JWT_ALGORITHMS
    ):
        try:
            signing_key = (
                _jwks_client(
                    _supabase_jwks_url()
                )
                .get_signing_key_from_jwt(
                    token
                )
            )
        except (
            PyJWKClientError,
            PyJWTError,
            OSError,
            ValueError,
        ) as exc:
            raise _authentication_error() from exc

        return (
            signing_key.key,
            algorithm,
        )

    raise _authentication_error(
        code="UNSUPPORTED_TOKEN_ALGORITHM",
        message=(
            "The access token uses an unsupported "
            "signing algorithm."
        ),
    )


def decode_supabase_access_token(
    token: str,
) -> DecodedSupabaseToken:
    """
    Validate a Supabase authenticated-user JWT.

    Legacy HS256 demo tokens are verified with the configured secret.
    Supabase ES256 or RS256 session tokens are verified against the
    project's cached JSON Web Key Set.
    """

    audience = os.getenv(
        "AUTH_JWT_AUDIENCE",
        "authenticated",
    ).strip()

    if not audience:
        raise RuntimeError(
            "AUTH_JWT_AUDIENCE is required."
        )

    key, algorithm = _verification_key(
        token
    )

    try:
        claims = jwt.decode(
            token,
            key,
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
        raise _authentication_error() from exc

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
