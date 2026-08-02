from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import settings


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    response_status: int | None
    response_headers: dict[str, str]
    response_body_excerpt: str | None
    evidence: dict[str, Any]


class DeliveryProviderError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        retryable: bool,
        response_status: int | None = None,
        response_headers: dict[str, str] | None = None,
        response_body_excerpt: str | None = None,
    ) -> None:
        super().__init__(message)

        self.code = code
        self.message = message
        self.retryable = retryable
        self.response_status = response_status
        self.response_headers = (
            response_headers or {}
        )
        self.response_body_excerpt = (
            response_body_excerpt
        )


def normalize_webhook_destination(
    value: str,
) -> str:
    normalized = value.strip()

    parsed = urlparse(normalized)

    if parsed.scheme not in {
        "http",
        "https",
    }:
        raise ValueError(
            "Webhook destinations must use HTTP or HTTPS."
        )

    if not parsed.hostname:
        raise ValueError(
            "Webhook destinations must include a hostname."
        )

    if parsed.username or parsed.password:
        raise ValueError(
            "Webhook destinations cannot include URL credentials."
        )

    allowed_hosts = (
        settings
        .notification_webhook_allowed_host_set
    )

    if (
        allowed_hosts
        and parsed.hostname.lower()
        not in allowed_hosts
    ):
        raise ValueError(
            "The webhook hostname is not in the configured allowlist."
        )

    return normalized


def normalize_email_destination(
    value: str,
) -> str:
    normalized = value.strip().lower()

    _, parsed_address = parseaddr(
        normalized
    )

    if (
        parsed_address != normalized
        or "@" not in parsed_address
    ):
        raise ValueError(
            "A valid email destination is required."
        )

    local_part, domain = (
        parsed_address.rsplit(
            "@",
            1,
        )
    )

    if (
        not local_part
        or "." not in domain
        or domain.startswith(".")
        or domain.endswith(".")
    ):
        raise ValueError(
            "A valid email destination is required."
        )

    return normalized


def retry_delay_seconds(
    *,
    attempt_number: int,
) -> int:
    base = max(
        1,
        settings
        .notification_retry_base_seconds,
    )

    maximum = max(
        base,
        settings
        .notification_retry_max_seconds,
    )

    delay = base * (
        2 ** max(
            0,
            attempt_number - 1,
        )
    )

    return min(
        delay,
        maximum,
    )


def webhook_status_is_retryable(
    status_code: int,
) -> bool:
    return (
        status_code in {
            408,
            425,
            429,
        }
        or 500 <= status_code <= 599
    )


async def send_webhook(
    *,
    destination: str,
    delivery_id: str,
    idempotency_key: str,
    payload: dict[str, Any],
) -> ProviderResult:
    body = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(
            ",",
            ":",
        ),
        sort_keys=True,
    ).encode(
        "utf-8"
    )

    signature = hmac.new(
        settings
        .notification_webhook_signing_secret
        .encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "User-Agent": (
            "DocuFlow-AP-Notifications/1.0"
        ),
        "X-DocuFlow-Event": (
            "accounting.export.ready"
        ),
        "X-DocuFlow-Delivery-ID": (
            delivery_id
        ),
        "X-DocuFlow-Idempotency-Key": (
            idempotency_key
        ),
        "X-DocuFlow-Signature": (
            f"sha256={signature}"
        ),
    }

    try:
        async with httpx.AsyncClient(
            timeout=(
                settings
                .notification_webhook_timeout_seconds
            ),
            follow_redirects=False,
        ) as client:
            response = await client.post(
                destination,
                content=body,
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        raise DeliveryProviderError(
            code="WEBHOOK_TIMEOUT",
            message=(
                "The webhook provider timed out."
            ),
            retryable=True,
        ) from exc
    except httpx.NetworkError as exc:
        raise DeliveryProviderError(
            code="WEBHOOK_NETWORK_ERROR",
            message=(
                "The webhook provider could not be reached."
            ),
            retryable=True,
        ) from exc

    response_headers = {
        key: value
        for key, value
        in response.headers.items()
    }

    body_excerpt = response.text[
        :1000
    ]

    if not (
        200
        <= response.status_code
        <= 299
    ):
        raise DeliveryProviderError(
            code=(
                "WEBHOOK_RETRYABLE_RESPONSE"
                if webhook_status_is_retryable(
                    response.status_code
                )
                else "WEBHOOK_REJECTED"
            ),
            message=(
                "The webhook provider returned "
                f"HTTP {response.status_code}."
            ),
            retryable=(
                webhook_status_is_retryable(
                    response.status_code
                )
            ),
            response_status=(
                response.status_code
            ),
            response_headers=(
                response_headers
            ),
            response_body_excerpt=(
                body_excerpt
            ),
        )

    return ProviderResult(
        provider="WEBHOOK_HTTP",
        response_status=(
            response.status_code
        ),
        response_headers=(
            response_headers
        ),
        response_body_excerpt=(
            body_excerpt
        ),
        evidence={
            "signature_algorithm": (
                "HMAC-SHA256"
            ),
            "request_body_sha256": (
                hashlib.sha256(
                    body
                ).hexdigest()
            ),
        },
    )


async def send_smtp_email(
    *,
    destination: str,
    subject: str,
    body_text: str,
    body_html: str | None,
) -> ProviderResult:
    message = EmailMessage()

    message["From"] = (
        settings.notification_email_from
    )

    message["To"] = destination
    message["Subject"] = subject

    message.set_content(
        body_text
    )

    if body_html:
        message.add_alternative(
            body_html,
            subtype="html",
        )

    try:
        await asyncio.to_thread(
            _send_smtp_message,
            message,
        )
    except (
        smtplib.SMTPException,
        OSError,
    ) as exc:
        raise DeliveryProviderError(
            code="SMTP_DELIVERY_ERROR",
            message=(
                "The SMTP provider could not deliver the email."
            ),
            retryable=True,
        ) from exc

    return ProviderResult(
        provider="EMAIL_SMTP",
        response_status=None,
        response_headers={},
        response_body_excerpt=None,
        evidence={
            "smtp_host": (
                settings
                .notification_smtp_host
            ),
            "smtp_port": (
                settings
                .notification_smtp_port
            ),
            "starttls": (
                settings
                .notification_smtp_starttls
            ),
        },
    )


def _send_smtp_message(
    message: EmailMessage,
) -> None:
    with smtplib.SMTP(
        host=(
            settings
            .notification_smtp_host
        ),
        port=(
            settings
            .notification_smtp_port
        ),
        timeout=(
            settings
            .notification_smtp_timeout_seconds
        ),
    ) as smtp:
        if (
            settings
            .notification_smtp_starttls
        ):
            smtp.starttls()

        if (
            settings
            .notification_smtp_username
        ):
            smtp.login(
                settings
                .notification_smtp_username,
                settings
                .notification_smtp_password,
            )

        smtp.send_message(
            message
        )
