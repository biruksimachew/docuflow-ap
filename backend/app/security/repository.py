from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.db.database import engine


async def get_active_role_assignment(
    user_id: str,
) -> dict[str, Any] | None:
    query = text(
        """
        select
            user_id,
            email,
            display_name,
            role,
            active
        from public.app_user_roles
        where
            user_id = cast(:user_id as uuid)
            and active = true
        limit 1
        """
    )

    async with engine.connect() as connection:
        result = await connection.execute(
            query,
            {
                "user_id": user_id,
            },
        )

        row = result.mappings().one_or_none()

    return (
        dict(row)
        if row is not None
        else None
    )


async def create_security_audit_event(
    *,
    request_id: str,
    user_id: str | None,
    email: str | None,
    app_role: str | None,
    event_type: str,
    method: str,
    path: str,
    status_code: int,
    reason: str,
    metadata: dict[str, Any],
) -> None:
    query = text(
        """
        insert into public.security_audit_events (
            request_id,
            user_id,
            email,
            app_role,
            event_type,
            method,
            path,
            status_code,
            reason,
            metadata
        )
        values (
            cast(:request_id as uuid),
            cast(:user_id as uuid),
            :email,
            :app_role,
            :event_type,
            :method,
            :path,
            :status_code,
            :reason,
            cast(:metadata as jsonb)
        )
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            query,
            {
                "request_id": request_id,
                "user_id": user_id,
                "email": email,
                "app_role": app_role,
                "event_type": event_type,
                "method": method,
                "path": path,
                "status_code": status_code,
                "reason": reason,
                "metadata": json.dumps(
                    metadata
                ),
            },
        )


async def list_security_audit_events(
    *,
    limit: int,
) -> list[dict[str, Any]]:
    query = text(
        """
        select
            id,
            request_id,
            user_id,
            email,
            app_role,
            event_type,
            method,
            path,
            status_code,
            reason,
            metadata,
            created_at
        from public.security_audit_events
        order by created_at desc
        limit :limit
        """
    )

    async with engine.connect() as connection:
        result = await connection.execute(
            query,
            {
                "limit": limit,
            },
        )

        rows = result.mappings().all()

    return [
        dict(row)
        for row in rows
    ]