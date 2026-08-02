from __future__ import annotations

import asyncio

from celery import shared_task

from app.db.database import engine
from app.services.notifications.service import (
    deliver_notification_once,
)


async def _deliver_and_dispose_engine(
    *,
    delivery_id: str,
) -> dict:
    """
    Execute one asynchronous notification delivery.

    Celery invokes this synchronous task through asyncio.run(), which creates
    a new event loop for every invocation. The shared SQLAlchemy AsyncEngine
    must therefore release pooled asyncpg connections before that loop closes,
    preventing connections from being reused by a different event loop.
    """

    try:
        return await deliver_notification_once(
            delivery_id=delivery_id
        )
    finally:
        await engine.dispose()


@shared_task(
    bind=True,
    name=(
        "app.workers.tasks."
        "deliver_notification"
    ),
    acks_late=True,
    reject_on_worker_lost=True,
)
def deliver_notification_task(
    self,
    delivery_id: str,
) -> dict:
    result = asyncio.run(
        _deliver_and_dispose_engine(
            delivery_id=delivery_id
        )
    )

    retry_after = result.get(
        "retry_after_seconds"
    )

    if (
        result.get("status")
        in {
            "RETRY_SCHEDULED",
            "DELIVERING",
        }
        and retry_after is not None
    ):
        self.apply_async(
            args=[
                delivery_id,
            ],
            countdown=max(
                1,
                int(retry_after),
            ),
        )

    return result