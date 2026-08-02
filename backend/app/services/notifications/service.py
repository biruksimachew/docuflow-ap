from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.core.config import settings
from app.db.database import engine
from app.security.models import AuthenticatedUser
from app.services.notifications.providers import (
    DeliveryProviderError,
    ProviderResult,
    normalize_email_destination,
    normalize_webhook_destination,
    retry_delay_seconds,
    send_smtp_email,
    send_webhook,
)


TEMPLATE_VERSION = (
    "accounting-export-ready-v1"
)


class NotificationNotFoundError(
    Exception
):
    """The requested export or notification does not exist."""


class NotificationConflictError(
    Exception
):
    """The requested notification transition is not allowed."""


async def create_notification_delivery(
    *,
    export_id: str,
    channel: str,
    destination: str,
    actor: AuthenticatedUser,
) -> dict[str, Any]:
    export_record = await _load_ready_export(
        export_id
    )

    normalized_channel = (
        channel.strip().upper()
    )

    if normalized_channel == "WEBHOOK":
        normalized_destination = (
            normalize_webhook_destination(
                destination
            )
        )

        provider = "WEBHOOK_HTTP"
    elif normalized_channel == "EMAIL":
        normalized_destination = (
            normalize_email_destination(
                destination
            )
        )

        configured_provider = (
            settings
            .notification_email_provider
            .strip()
            .upper()
        )

        if configured_provider == "LOCAL_SINK":
            provider = (
                "EMAIL_LOCAL_SINK"
            )
        elif configured_provider == "SMTP":
            provider = "EMAIL_SMTP"
        else:
            raise RuntimeError(
                "NOTIFICATION_EMAIL_PROVIDER must be "
                "LOCAL_SINK or SMTP."
            )
    else:
        raise ValueError(
            "Notification channel must be WEBHOOK or EMAIL."
        )

    destination_hash = hashlib.sha256(
        normalized_destination
        .encode("utf-8")
    ).hexdigest()

    idempotency_key = hashlib.sha256(
        "|".join(
            (
                TEMPLATE_VERSION,
                export_id,
                normalized_channel,
                destination_hash,
            )
        ).encode("utf-8")
    ).hexdigest()

    payload = _notification_payload(
        export_record
    )

    request_headers = (
        {
            "Content-Type": (
                "application/json"
            ),
            "X-DocuFlow-Event": (
                "accounting.export.ready"
            ),
        }
        if normalized_channel
        == "WEBHOOK"
        else {}
    )

    insert_query = text(
        """
        insert into public.notification_deliveries (
            accounting_export_id,
            document_id,
            channel,
            provider,
            destination,
            destination_hash,
            template_version,
            idempotency_key,
            status,
            payload,
            request_headers,
            max_attempts,
            created_by_user_id,
            created_by_email,
            created_by_role
        )
        values (
            cast(:export_id as uuid),
            cast(:document_id as uuid),
            :channel,
            :provider,
            :destination,
            :destination_hash,
            :template_version,
            :idempotency_key,
            'PENDING',
            cast(:payload as jsonb),
            cast(:request_headers as jsonb),
            :max_attempts,
            cast(:actor_user_id as uuid),
            :actor_email,
            :actor_role
        )
        on conflict (idempotency_key)
        do nothing
        returning *
        """
    )

    select_query = text(
        """
        select *
        from public.notification_deliveries
        where idempotency_key =
            :idempotency_key
        limit 1
        """
    )

    async with engine.begin() as connection:
        result = await connection.execute(
            insert_query,
            {
                "export_id": export_id,
                "document_id": str(
                    export_record[
                        "document_id"
                    ]
                ),
                "channel": (
                    normalized_channel
                ),
                "provider": provider,
                "destination": (
                    normalized_destination
                ),
                "destination_hash": (
                    destination_hash
                ),
                "template_version": (
                    TEMPLATE_VERSION
                ),
                "idempotency_key": (
                    idempotency_key
                ),
                "payload": json.dumps(
                    payload
                ),
                "request_headers": (
                    json.dumps(
                        request_headers
                    )
                ),
                "max_attempts": max(
                    1,
                    settings
                    .notification_max_attempts,
                ),
                "actor_user_id": (
                    actor.user_id
                ),
                "actor_email": actor.email,
                "actor_role": actor.role,
            },
        )

        inserted = (
            result.mappings().one_or_none()
        )

        if inserted is not None:
            delivery = dict(
                inserted
            )

            created = True
        else:
            existing_result = (
                await connection.execute(
                    select_query,
                    {
                        "idempotency_key": (
                            idempotency_key
                        ),
                    },
                )
            )

            delivery = dict(
                existing_result
                .mappings()
                .one()
            )

            created = False

    should_enqueue = (
        created
        or delivery["status"]
        == "PENDING"
    )

    return {
        "delivery": _json_safe_dict(
            delivery
        ),
        "idempotent_reuse": (
            not created
        ),
        "should_enqueue": (
            should_enqueue
        ),
    }


async def list_export_notifications(
    export_id: str,
) -> list[dict[str, Any]]:
    query = text(
        """
        select
            id,
            accounting_export_id,
            document_id,
            channel,
            provider,
            destination,
            destination_hash,
            template_version,
            idempotency_key,
            status,
            attempt_count,
            max_attempts,
            last_attempt_at,
            next_attempt_at,
            delivered_at,
            last_error_code,
            last_error_message,
            created_by_user_id,
            created_by_email,
            created_by_role,
            created_at,
            updated_at
        from public.notification_deliveries
        where accounting_export_id =
            cast(:export_id as uuid)
        order by created_at desc
        """
    )

    async with engine.connect() as connection:
        result = await connection.execute(
            query,
            {
                "export_id": export_id,
            },
        )

        rows = result.mappings().all()

    return [
        _json_safe_dict(
            dict(row)
        )
        for row in rows
    ]


async def get_notification_snapshot(
    delivery_id: str,
) -> dict[str, Any]:
    delivery_query = text(
        """
        select *
        from public.notification_deliveries
        where id =
            cast(:delivery_id as uuid)
        limit 1
        """
    )

    attempts_query = text(
        """
        select *
        from public.notification_delivery_attempts
        where notification_delivery_id =
            cast(:delivery_id as uuid)
        order by attempt_number asc
        """
    )

    email_query = text(
        """
        select *
        from public.notification_email_sink_messages
        where notification_delivery_id =
            cast(:delivery_id as uuid)
        limit 1
        """
    )

    async with engine.connect() as connection:
        result = await connection.execute(
            delivery_query,
            {
                "delivery_id": delivery_id,
            },
        )

        delivery = (
            result.mappings().one_or_none()
        )

        if delivery is None:
            raise NotificationNotFoundError()

        attempt_result = (
            await connection.execute(
                attempts_query,
                {
                    "delivery_id": (
                        delivery_id
                    ),
                },
            )
        )

        email_result = (
            await connection.execute(
                email_query,
                {
                    "delivery_id": (
                        delivery_id
                    ),
                },
            )
        )

        attempts = (
            attempt_result
            .mappings()
            .all()
        )

        email_message = (
            email_result
            .mappings()
            .one_or_none()
        )

    return {
        "delivery": _json_safe_dict(
            dict(delivery)
        ),
        "attempts": [
            _json_safe_dict(
                dict(row)
            )
            for row in attempts
        ],
        "local_email_message": (
            _json_safe_dict(
                dict(email_message)
            )
            if email_message
            is not None
            else None
        ),
    }


async def requeue_notification_delivery(
    delivery_id: str,
) -> dict[str, Any]:
    load_query = text(
        """
        select *
        from public.notification_deliveries
        where id =
            cast(:delivery_id as uuid)
        for update
        """
    )

    update_query = text(
        """
        update public.notification_deliveries
        set
            status = 'PENDING',
            max_attempts = greatest(
                max_attempts,
                attempt_count + 1
            ),
            next_attempt_at = null,
            last_error_code = null,
            last_error_message = null
        where id =
            cast(:delivery_id as uuid)
        returning *
        """
    )

    async with engine.begin() as connection:
        result = await connection.execute(
            load_query,
            {
                "delivery_id": delivery_id,
            },
        )

        current = (
            result.mappings().one_or_none()
        )

        if current is None:
            raise NotificationNotFoundError()

        if current["status"] == "SUCCEEDED":
            raise NotificationConflictError(
                "A successful notification cannot be retried."
            )

        if current["status"] == "DELIVERING":
            raise NotificationConflictError(
                "The notification is currently being delivered."
            )

        updated_result = (
            await connection.execute(
                update_query,
                {
                    "delivery_id": (
                        delivery_id
                    ),
                },
            )
        )

        updated = dict(
            updated_result
            .mappings()
            .one()
        )

    return _json_safe_dict(
        updated
    )


async def deliver_notification_once(
    *,
    delivery_id: str,
) -> dict[str, Any]:
    attempt = await _start_attempt(
        delivery_id
    )

    if not attempt["claimed"]:
        return attempt

    delivery = attempt["delivery"]

    attempt_number = int(
        attempt["attempt_number"]
    )

    try:
        provider_result = (
            await _deliver_with_provider(
                delivery
            )
        )

        completed = await _complete_attempt(
            delivery=delivery,
            attempt_number=attempt_number,
            provider_result=(
                provider_result
            ),
        )

        return {
            "status": "SUCCEEDED",
            "delivery_id": delivery_id,
            "attempt_number": (
                attempt_number
            ),
            "retry_after_seconds": None,
            "delivery": completed,
        }

    except DeliveryProviderError as exc:
        return await _fail_attempt(
            delivery=delivery,
            attempt_number=attempt_number,
            error=exc,
        )
    except Exception as exc:
        provider_error = (
            DeliveryProviderError(
                code=type(exc).__name__,
                message=str(exc)[:2000],
                retryable=True,
            )
        )

        return await _fail_attempt(
            delivery=delivery,
            attempt_number=attempt_number,
            error=provider_error,
        )


async def record_test_webhook_receipt(
    *,
    token: str,
    mode: str,
    request_headers: dict[str, str],
    request_body: dict[str, Any],
) -> dict[str, Any]:
    normalized_mode = (
        mode.strip().lower()
    )

    if normalized_mode not in {
        "success",
        "fail-once",
    }:
        raise ValueError(
            "Test webhook mode must be success or fail-once."
        )

    count_query = text(
        """
        select count(*) as receipt_count
        from public.notification_test_webhook_receipts
        where
            token = :token
            and mode = :mode
        """
    )

    insert_query = text(
        """
        insert into public.notification_test_webhook_receipts (
            token,
            mode,
            request_headers,
            request_body,
            response_status
        )
        values (
            :token,
            :mode,
            cast(:request_headers as jsonb),
            cast(:request_body as jsonb),
            :response_status
        )
        returning *
        """
    )

    async with engine.begin() as connection:
        count_result = await connection.execute(
            count_query,
            {
                "token": token,
                "mode": normalized_mode,
            },
        )

        prior_count = int(
            count_result
            .mappings()
            .one()[
                "receipt_count"
            ]
        )

        response_status = (
            503
            if (
                normalized_mode
                == "fail-once"
                and prior_count == 0
            )
            else 200
        )

        result = await connection.execute(
            insert_query,
            {
                "token": token,
                "mode": normalized_mode,
                "request_headers": (
                    json.dumps(
                        request_headers
                    )
                ),
                "request_body": (
                    json.dumps(
                        request_body
                    )
                ),
                "response_status": (
                    response_status
                ),
            },
        )

        receipt = dict(
            result.mappings().one()
        )

    return {
        "receipt": _json_safe_dict(
            receipt
        ),
        "response_status": (
            response_status
        ),
        "attempt_number": (
            prior_count + 1
        ),
    }


async def _load_ready_export(
    export_id: str,
) -> dict[str, Any]:
    query = text(
        """
        select *
        from public.accounting_exports
        where id =
            cast(:export_id as uuid)
        limit 1
        """
    )

    async with engine.connect() as connection:
        result = await connection.execute(
            query,
            {
                "export_id": export_id,
            },
        )

        row = result.mappings().one_or_none()

    if row is None:
        raise NotificationNotFoundError()

    export_record = dict(row)

    if (
        export_record["status"]
        != "READY"
        or not export_record[
            "payload_text"
        ]
    ):
        raise NotificationConflictError(
            "Only ready accounting exports can be delivered."
        )

    return _json_safe_dict(
        export_record
    )


def _notification_payload(
    export_record: dict[str, Any],
) -> dict[str, Any]:
    export_format = export_record[
        "export_format"
    ]

    raw_payload = export_record[
        "payload_text"
    ]

    if export_format == "JSON":
        accounting_payload: Any = (
            json.loads(
                raw_payload
            )
        )
    else:
        accounting_payload = (
            raw_payload
        )

    return {
        "event": (
            "accounting.export.ready"
        ),
        "event_version": "1.0",
        "export": {
            "id": export_record["id"],
            "document_id": (
                export_record[
                    "document_id"
                ]
            ),
            "format": export_format,
            "schema_version": (
                export_record[
                    "schema_version"
                ]
            ),
            "source_kind": (
                export_record[
                    "source_kind"
                ]
            ),
            "source_version": (
                export_record[
                    "source_version"
                ]
            ),
            "file_name": (
                export_record[
                    "file_name"
                ]
            ),
            "content_type": (
                export_record[
                    "content_type"
                ]
            ),
            "payload_sha256": (
                export_record[
                    "payload_sha256"
                ]
            ),
            "row_count": (
                export_record[
                    "row_count"
                ]
            ),
            "download_url": (
                f"{settings.public_api_base_url}"
                f"/api/v1/exports/"
                f"{export_record['id']}"
                "/download"
            ),
        },
        "accounting_payload": (
            accounting_payload
        ),
    }


async def _start_attempt(
    delivery_id: str,
) -> dict[str, Any]:
    load_query = text(
        """
        select *
        from public.notification_deliveries
        where id =
            cast(:delivery_id as uuid)
        for update
        """
    )

    update_query = text(
        """
        update public.notification_deliveries
        set
            status = 'DELIVERING',
            attempt_count =
                attempt_count + 1,
            last_attempt_at = now(),
            next_attempt_at = null
        where id =
            cast(:delivery_id as uuid)
        returning *
        """
    )

    insert_attempt = text(
        """
        insert into public.notification_delivery_attempts (
            notification_delivery_id,
            attempt_number,
            status,
            request_snapshot
        )
        values (
            cast(:delivery_id as uuid),
            :attempt_number,
            'STARTED',
            cast(:request_snapshot as jsonb)
        )
        """
    )

    async with engine.begin() as connection:
        result = await connection.execute(
            load_query,
            {
                "delivery_id": delivery_id,
            },
        )

        current = (
            result.mappings().one_or_none()
        )

        if current is None:
            raise NotificationNotFoundError()

        if current["status"] in {
            "SUCCEEDED",
            "FAILED",
        }:
            return {
                "claimed": False,
                "status": current[
                    "status"
                ],
                "delivery_id": delivery_id,
                "retry_after_seconds": None,
            }

        now = datetime.now(
            timezone.utc
        )

        if current["status"] == "DELIVERING":
            stale_seconds = max(
                30,
                settings
                .notification_delivery_stale_seconds,
            )

            last_attempt_at = current[
                "last_attempt_at"
            ]

            age_seconds = (
                int(
                    (
                        now
                        - last_attempt_at
                    ).total_seconds()
                )
                if last_attempt_at
                is not None
                else stale_seconds
            )

            if age_seconds < stale_seconds:
                return {
                    "claimed": False,
                    "status": "DELIVERING",
                    "delivery_id": delivery_id,
                    "retry_after_seconds": max(
                        1,
                        stale_seconds
                        - age_seconds,
                    ),
                }

            if (
                int(current["attempt_count"])
                >= int(current["max_attempts"])
            ):
                await connection.execute(
                    text(
                        """
                        update public.notification_delivery_attempts
                        set
                            status = 'FAILED',
                            retryable = false,
                            error_code =
                                'STALE_DELIVERY_EXHAUSTED',
                            error_message =
                                'A worker stopped during delivery and '
                                'the maximum attempt count was reached.',
                            completed_at = now()
                        where
                            notification_delivery_id =
                                cast(:delivery_id as uuid)
                            and status = 'STARTED'
                        """
                    ),
                    {
                        "delivery_id": (
                            delivery_id
                        ),
                    },
                )

                await connection.execute(
                    text(
                        """
                        update public.notification_deliveries
                        set
                            status = 'FAILED',
                            last_error_code =
                                'STALE_DELIVERY_EXHAUSTED',
                            last_error_message =
                                'A worker stopped during delivery and '
                                'the maximum attempt count was reached.'
                        where id =
                            cast(:delivery_id as uuid)
                        """
                    ),
                    {
                        "delivery_id": (
                            delivery_id
                        ),
                    },
                )

                return {
                    "claimed": False,
                    "status": "FAILED",
                    "delivery_id": delivery_id,
                    "retry_after_seconds": None,
                }

            await connection.execute(
                text(
                    """
                    update public.notification_delivery_attempts
                    set
                        status = 'FAILED',
                        retryable = true,
                        retry_after_seconds = 0,
                        error_code =
                            'STALE_DELIVERY_RECOVERED',
                        error_message =
                            'A previous worker stopped before '
                            'completing the delivery.',
                        completed_at = now()
                    where
                        notification_delivery_id =
                            cast(:delivery_id as uuid)
                        and status = 'STARTED'
                    """
                ),
                {
                    "delivery_id": (
                        delivery_id
                    ),
                },
            )

        next_attempt_at = current[
            "next_attempt_at"
        ]

        if (
            current["status"]
            == "RETRY_SCHEDULED"
            and next_attempt_at
            is not None
            and next_attempt_at > now
        ):
            seconds = max(
                1,
                int(
                    (
                        next_attempt_at
                        - now
                    ).total_seconds()
                ),
            )

            return {
                "claimed": False,
                "status": (
                    "RETRY_SCHEDULED"
                ),
                "delivery_id": delivery_id,
                "retry_after_seconds": (
                    seconds
                ),
            }

        updated_result = (
            await connection.execute(
                update_query,
                {
                    "delivery_id": (
                        delivery_id
                    ),
                },
            )
        )

        updated = dict(
            updated_result
            .mappings()
            .one()
        )

        attempt_number = int(
            updated["attempt_count"]
        )

        await connection.execute(
            insert_attempt,
            {
                "delivery_id": (
                    delivery_id
                ),
                "attempt_number": (
                    attempt_number
                ),
                "request_snapshot": (
                    json.dumps(
                        {
                            "channel": (
                                updated[
                                    "channel"
                                ]
                            ),
                            "provider": (
                                updated[
                                    "provider"
                                ]
                            ),
                            "destination_hash": (
                                updated[
                                    "destination_hash"
                                ]
                            ),
                            "template_version": (
                                updated[
                                    "template_version"
                                ]
                            ),
                            "idempotency_key": (
                                updated[
                                    "idempotency_key"
                                ]
                            ),
                        }
                    )
                ),
            },
        )

    return {
        "claimed": True,
        "delivery": _json_safe_dict(
            updated
        ),
        "attempt_number": (
            attempt_number
        ),
    }


async def _deliver_with_provider(
    delivery: dict[str, Any],
) -> ProviderResult:
    if delivery["provider"] == "WEBHOOK_HTTP":
        return await send_webhook(
            destination=delivery[
                "destination"
            ],
            delivery_id=delivery["id"],
            idempotency_key=delivery[
                "idempotency_key"
            ],
            payload=delivery["payload"],
        )

    subject, body_text, body_html = (
        _render_email(
            delivery
        )
    )

    if (
        delivery["provider"]
        == "EMAIL_LOCAL_SINK"
    ):
        await _store_local_email(
            delivery_id=delivery["id"],
            recipient=delivery[
                "destination"
            ],
            sender=(
                settings
                .notification_email_from
            ),
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )

        return ProviderResult(
            provider="EMAIL_LOCAL_SINK",
            response_status=None,
            response_headers={},
            response_body_excerpt=None,
            evidence={
                "local_sink": True,
                "recipient": delivery[
                    "destination"
                ],
            },
        )

    if delivery["provider"] == "EMAIL_SMTP":
        return await send_smtp_email(
            destination=delivery[
                "destination"
            ],
            subject=subject,
            body_text=body_text,
            body_html=body_html,
        )

    raise DeliveryProviderError(
        code="UNSUPPORTED_NOTIFICATION_PROVIDER",
        message=(
            "The configured notification provider is unsupported."
        ),
        retryable=False,
    )


def _render_email(
    delivery: dict[str, Any],
) -> tuple[str, str, str]:
    export = delivery["payload"][
        "export"
    ]

    subject = (
        "DocuFlow AP export ready: "
        f"{export['file_name']}"
    )

    body_text = "\n".join(
        (
            "An approved invoice export is ready.",
            "",
            f"Document ID: {export['document_id']}",
            f"Export ID: {export['id']}",
            f"Format: {export['format']}",
            f"Source: {export['source_kind']}",
            f"SHA-256: {export['payload_sha256']}",
            f"Download: {export['download_url']}",
        )
    )

    body_html = (
        "<p>An approved invoice export is ready.</p>"
        "<ul>"
        f"<li>Document ID: {export['document_id']}</li>"
        f"<li>Export ID: {export['id']}</li>"
        f"<li>Format: {export['format']}</li>"
        f"<li>Source: {export['source_kind']}</li>"
        f"<li>SHA-256: {export['payload_sha256']}</li>"
        "</ul>"
        f"<p><a href=\"{export['download_url']}\">"
        "Download accounting export</a></p>"
    )

    return (
        subject,
        body_text,
        body_html,
    )


async def _store_local_email(
    *,
    delivery_id: str,
    recipient: str,
    sender: str,
    subject: str,
    body_text: str,
    body_html: str | None,
) -> None:
    query = text(
        """
        insert into public.notification_email_sink_messages (
            notification_delivery_id,
            recipient,
            sender,
            subject,
            body_text,
            body_html
        )
        values (
            cast(:delivery_id as uuid),
            :recipient,
            :sender,
            :subject,
            :body_text,
            :body_html
        )
        on conflict (notification_delivery_id)
        do nothing
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            query,
            {
                "delivery_id": delivery_id,
                "recipient": recipient,
                "sender": sender,
                "subject": subject,
                "body_text": body_text,
                "body_html": body_html,
            },
        )


async def _complete_attempt(
    *,
    delivery: dict[str, Any],
    attempt_number: int,
    provider_result: ProviderResult,
) -> dict[str, Any]:
    update_attempt = text(
        """
        update public.notification_delivery_attempts
        set
            status = 'SUCCEEDED',
            response_status =
                :response_status,
            response_headers =
                cast(:response_headers as jsonb),
            response_body_excerpt =
                :response_body_excerpt,
            retryable = false,
            retry_after_seconds = null,
            completed_at = now()
        where
            notification_delivery_id =
                cast(:delivery_id as uuid)
            and attempt_number =
                :attempt_number
        """
    )

    update_delivery = text(
        """
        update public.notification_deliveries
        set
            status = 'SUCCEEDED',
            delivered_at = now(),
            next_attempt_at = null,
            last_error_code = null,
            last_error_message = null,
            request_headers =
                request_headers
                || cast(:provider_evidence as jsonb)
        where id =
            cast(:delivery_id as uuid)
        returning *
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            update_attempt,
            {
                "delivery_id": delivery["id"],
                "attempt_number": (
                    attempt_number
                ),
                "response_status": (
                    provider_result
                    .response_status
                ),
                "response_headers": (
                    json.dumps(
                        provider_result
                        .response_headers
                    )
                ),
                "response_body_excerpt": (
                    provider_result
                    .response_body_excerpt
                ),
            },
        )

        result = await connection.execute(
            update_delivery,
            {
                "delivery_id": delivery["id"],
                "provider_evidence": (
                    json.dumps(
                        {
                            "provider": (
                                provider_result
                                .provider
                            ),
                            "evidence": (
                                provider_result
                                .evidence
                            ),
                        }
                    )
                ),
            },
        )

        updated = dict(
            result.mappings().one()
        )

    return _json_safe_dict(
        updated
    )


async def _fail_attempt(
    *,
    delivery: dict[str, Any],
    attempt_number: int,
    error: DeliveryProviderError,
) -> dict[str, Any]:
    max_attempts = int(
        delivery["max_attempts"]
    )

    retryable = (
        error.retryable
        and attempt_number
        < max_attempts
    )

    retry_after = (
        retry_delay_seconds(
            attempt_number=attempt_number
        )
        if retryable
        else None
    )

    next_attempt_at = (
        datetime.now(
            timezone.utc
        )
        + timedelta(
            seconds=retry_after
        )
        if retry_after is not None
        else None
    )

    final_status = (
        "RETRY_SCHEDULED"
        if retryable
        else "FAILED"
    )

    update_attempt = text(
        """
        update public.notification_delivery_attempts
        set
            status = 'FAILED',
            response_status =
                :response_status,
            response_headers =
                cast(:response_headers as jsonb),
            response_body_excerpt =
                :response_body_excerpt,
            retryable = :retryable,
            retry_after_seconds =
                :retry_after_seconds,
            error_code = :error_code,
            error_message = :error_message,
            completed_at = now()
        where
            notification_delivery_id =
                cast(:delivery_id as uuid)
            and attempt_number =
                :attempt_number
        """
    )

    update_delivery = text(
        """
        update public.notification_deliveries
        set
            status = :status,
            next_attempt_at =
                :next_attempt_at,
            last_error_code =
                :error_code,
            last_error_message =
                :error_message
        where id =
            cast(:delivery_id as uuid)
        returning *
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            update_attempt,
            {
                "delivery_id": delivery["id"],
                "attempt_number": (
                    attempt_number
                ),
                "response_status": (
                    error.response_status
                ),
                "response_headers": (
                    json.dumps(
                        error.response_headers
                    )
                ),
                "response_body_excerpt": (
                    error
                    .response_body_excerpt
                ),
                "retryable": retryable,
                "retry_after_seconds": (
                    retry_after
                ),
                "error_code": error.code,
                "error_message": (
                    error.message
                ),
            },
        )

        result = await connection.execute(
            update_delivery,
            {
                "delivery_id": delivery["id"],
                "status": final_status,
                "next_attempt_at": (
                    next_attempt_at
                ),
                "error_code": error.code,
                "error_message": (
                    error.message
                ),
            },
        )

        updated = dict(
            result.mappings().one()
        )

    return {
        "status": final_status,
        "delivery_id": delivery["id"],
        "attempt_number": attempt_number,
        "retry_after_seconds": (
            retry_after
        ),
        "delivery": _json_safe_dict(
            updated
        ),
    }


def _json_safe_dict(
    value: dict[str, Any],
) -> dict[str, Any]:
    return {
        key: _json_safe(item)
        for key, item in value.items()
    }


def _json_safe(
    value: Any,
) -> Any:
    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, Decimal):
        return format(value, "f")

    if isinstance(
        value,
        (
            date,
            datetime,
        ),
    ):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            key: _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _json_safe(item)
            for item in value
        ]

    return value
