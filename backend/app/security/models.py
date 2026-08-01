from __future__ import annotations

from dataclasses import dataclass
from typing import Any


VALID_APP_ROLES = frozenset(
    {
        "AP_CLERK",
        "REVIEWER",
        "ADMIN",
    }
)


@dataclass(frozen=True)
class DecodedSupabaseToken:
    """Validated identity claims from a Supabase-compatible JWT."""

    subject: str
    email: str | None
    token_role: str

    issued_at: int | None
    expires_at: int

    claims: dict[str, Any]


@dataclass(frozen=True)
class AuthenticatedUser:
    """Authenticated user with authoritative application role."""

    user_id: str
    email: str
    display_name: str
    role: str

    token_role: str
    token_expires_at: int


def role_allowed(
    user_role: str,
    allowed_roles: set[str],
) -> bool:
    return (
        user_role in VALID_APP_ROLES
        and user_role in allowed_roles
    )