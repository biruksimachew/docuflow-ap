from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)


@dataclass(frozen=True)
class LocalAuthUser:
    email: str
    display_name: str
    role: str


LOCAL_USERS = (
    LocalAuthUser(
        email=(
            "ap.clerk@docuflow.local"
        ),
        display_name=(
            "Authenticated AP Clerk"
        ),
        role="AP_CLERK",
    ),
    LocalAuthUser(
        email=(
            "reviewer.user@docuflow.local"
        ),
        display_name=(
            "Authenticated AP Reviewer"
        ),
        role="REVIEWER",
    ),
    LocalAuthUser(
        email=(
            "administrator@docuflow.local"
        ),
        display_name=(
            "Authenticated Administrator"
        ),
        role="ADMIN",
    ),
)


def _required_environment(
    name: str,
) -> str:
    value = os.getenv(
        name,
        "",
    ).strip()

    if (
        not value or
        value.startswith("replace")
    ):
        raise RuntimeError(
            f"{name} is required."
        )

    return value


def _user_payload(
    user: LocalAuthUser,
    password: str,
) -> dict[str, Any]:
    return {
        "email": user.email,
        "password": password,
        "email_confirm": True,
        "user_metadata": {
            "display_name": (
                user.display_name
            ),
        },
        "app_metadata": {
            "docuflow_role": (
                user.role
            ),
        },
    }


def _unwrap_user(
    payload: Any,
) -> dict[str, Any]:
    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            "Supabase returned an invalid user payload."
        )

    nested = payload.get(
        "user"
    )

    if isinstance(
        nested,
        dict,
    ):
        return nested

    return payload


async def _list_auth_users(
    client: httpx.AsyncClient,
) -> list[dict[str, Any]]:
    response = await client.get(
        "/auth/v1/admin/users",
        params={
            "page": 1,
            "per_page": 1000,
        },
    )

    response.raise_for_status()

    payload = response.json()

    if isinstance(
        payload,
        dict,
    ):
        users = payload.get(
            "users",
            [],
        )
    elif isinstance(
        payload,
        list,
    ):
        users = payload
    else:
        users = []

    return [
        user
        for user in users
        if isinstance(
            user,
            dict,
        )
    ]


async def _ensure_auth_user(
    client: httpx.AsyncClient,
    existing_users: list[
        dict[str, Any]
    ],
    user: LocalAuthUser,
    password: str,
) -> dict[str, Any]:
    existing = next(
        (
            item
            for item in existing_users
            if str(
                item.get(
                    "email",
                    "",
                )
            ).lower() == (
                user.email.lower()
            )
        ),
        None,
    )

    payload = _user_payload(
        user,
        password,
    )

    if existing is None:
        response = await client.post(
            "/auth/v1/admin/users",
            json=payload,
        )
    else:
        user_id = str(
            existing.get(
                "id",
                "",
            )
        )

        if not user_id:
            raise RuntimeError(
                "Existing Supabase user has no id."
            )

        response = await client.put(
            (
                "/auth/v1/admin/users/"
                f"{user_id}"
            ),
            json=payload,
        )

    if not response.is_success:
        raise RuntimeError(
            "Supabase user provisioning failed "
            f"for {user.email}: "
            f"HTTP {response.status_code}."
        )

    return _unwrap_user(
        response.json()
    )


async def _upsert_role(
    engine: AsyncEngine,
    *,
    user_id: str,
    user: LocalAuthUser,
) -> None:
    query = text(
        """
        insert into public.app_user_roles (
            user_id,
            email,
            display_name,
            role,
            active
        )
        values (
            cast(:user_id as uuid),
            :email,
            :display_name,
            :role,
            true
        )
        on conflict (email)
        do update set
            user_id = excluded.user_id,
            display_name =
                excluded.display_name,
            role = excluded.role,
            active = true,
            updated_at = now()
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            query,
            {
                "user_id": user_id,
                "email": user.email,
                "display_name": (
                    user.display_name
                ),
                "role": user.role,
            },
        )


async def provision_local_auth_users() -> list[
    dict[str, str]
]:
    app_env = os.getenv(
        "APP_ENV",
        "local",
    ).strip().lower()

    if app_env != "local":
        raise RuntimeError(
            "Local auth provisioning is disabled "
            "outside APP_ENV=local."
        )

    supabase_url = _required_environment(
        "SUPABASE_URL"
    ).rstrip("/")

    service_role_key = (
        _required_environment(
            "SUPABASE_SERVICE_ROLE_KEY"
        )
    )

    database_url = _required_environment(
        "DATABASE_URL"
    )

    password = os.getenv(
        "DOCUFLOW_LOCAL_AUTH_PASSWORD",
        "DocuFlowLocal!2026",
    )

    if len(password) < 12:
        raise RuntimeError(
            "DOCUFLOW_LOCAL_AUTH_PASSWORD must "
            "contain at least 12 characters."
        )

    headers = {
        "Accept": "application/json",
        "Content-Type":
            "application/json",
        "apikey": service_role_key,
        "Authorization":
            f"Bearer {service_role_key}",
    }

    engine = create_async_engine(
        database_url,
        pool_pre_ping=True,
    )

    provisioned: list[
        dict[str, str]
    ] = []

    try:
        async with httpx.AsyncClient(
            base_url=supabase_url,
            headers=headers,
            timeout=30,
        ) as client:
            existing_users = (
                await _list_auth_users(
                    client
                )
            )

            for user in LOCAL_USERS:
                auth_user = (
                    await _ensure_auth_user(
                        client,
                        existing_users,
                        user,
                        password,
                    )
                )

                user_id = str(
                    auth_user.get(
                        "id",
                        "",
                    )
                )

                if not user_id:
                    raise RuntimeError(
                        "Provisioned Supabase user "
                        "has no id."
                    )

                await _upsert_role(
                    engine,
                    user_id=user_id,
                    user=user,
                )

                provisioned.append(
                    {
                        "email": (
                            user.email
                        ),
                        "role": user.role,
                        "user_id": user_id,
                    }
                )
    finally:
        await engine.dispose()

    return provisioned


def main() -> None:
    provisioned = asyncio.run(
        provision_local_auth_users()
    )

    print(
        {
            "status": "passed",
            "provisioned_count": len(
                provisioned
            ),
            "users": [
                {
                    "email": item[
                        "email"
                    ],
                    "role": item[
                        "role"
                    ],
                }
                for item in provisioned
            ],
        }
    )


if __name__ == "__main__":
    main()
