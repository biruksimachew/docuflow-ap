from datetime import (
    datetime,
    timedelta,
    timezone,
)

import jwt
import pytest

from app.security.errors import (
    AuthenticationError,
)
from app.security.jwt import (
    decode_supabase_access_token,
)
from app.security.models import (
    role_allowed,
)


TEST_SECRET = (
    "test-secret-token-with-at-least-32-characters"
)

TEST_SUBJECT = (
    "90000000-0000-0000-0000-000000000001"
)


def token(
    *,
    audience: str = "authenticated",
    expires_in_seconds: int = 3600,
    token_role: str = "authenticated",
) -> str:
    now = datetime.now(
        timezone.utc
    )

    return jwt.encode(
        {
            "sub": TEST_SUBJECT,
            "email": (
                "clerk@docuflow.local"
            ),
            "aud": audience,
            "role": token_role,
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
        },
        TEST_SECRET,
        algorithm="HS256",
    )


def configure(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "SUPABASE_JWT_SECRET",
        TEST_SECRET,
    )

    monkeypatch.setenv(
        "AUTH_JWT_ALGORITHM",
        "HS256",
    )

    monkeypatch.setenv(
        "AUTH_JWT_AUDIENCE",
        "authenticated",
    )


def test_valid_supabase_token_is_decoded(
    monkeypatch,
) -> None:
    configure(
        monkeypatch
    )

    decoded = decode_supabase_access_token(
        token()
    )

    assert (
        decoded.subject
        == TEST_SUBJECT
    )

    assert (
        decoded.email
        == "clerk@docuflow.local"
    )

    assert (
        decoded.token_role
        == "authenticated"
    )


def test_expired_token_is_rejected(
    monkeypatch,
) -> None:
    configure(
        monkeypatch
    )

    with pytest.raises(
        AuthenticationError
    ):
        decode_supabase_access_token(
            token(
                expires_in_seconds=-60
            )
        )


def test_wrong_audience_is_rejected(
    monkeypatch,
) -> None:
    configure(
        monkeypatch
    )

    with pytest.raises(
        AuthenticationError
    ):
        decode_supabase_access_token(
            token(
                audience="another-service"
            )
        )


def test_service_role_token_is_rejected(
    monkeypatch,
) -> None:
    configure(
        monkeypatch
    )

    with pytest.raises(
        AuthenticationError
    ):
        decode_supabase_access_token(
            token(
                token_role="service_role"
            )
        )


def test_application_role_permissions() -> None:
    assert role_allowed(
        "REVIEWER",
        {
            "REVIEWER",
            "ADMIN",
        },
    )

    assert role_allowed(
        "ADMIN",
        {
            "ADMIN",
        },
    )

    assert not role_allowed(
        "AP_CLERK",
        {
            "REVIEWER",
            "ADMIN",
        },
    )