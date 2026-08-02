import pytest

from app.services.notifications.providers import (
    normalize_email_destination,
    normalize_webhook_destination,
    retry_delay_seconds,
    webhook_status_is_retryable,
)
from app.services.notifications.service import (
    _notification_payload,
)


def ready_export() -> dict:
    return {
        "id": (
            "00000000-0000-0000-0000-000000000001"
        ),
        "document_id": (
            "00000000-0000-0000-0000-000000000002"
        ),
        "export_format": "JSON",
        "schema_version": (
            "accounting-export-v1"
        ),
        "source_kind": "CANONICAL",
        "source_version": (
            "decision-run:test"
        ),
        "file_name": (
            "docuflow-INV-1001.json"
        ),
        "content_type": (
            "application/json"
        ),
        "payload_sha256": "a" * 64,
        "row_count": 2,
        "payload_text": (
            '{"invoice":{"header":'
            '{"invoice_number":"INV-1001"}}}'
        ),
    }


def test_local_webhook_destination_is_allowed() -> None:
    destination = normalize_webhook_destination(
        (
            "http://api:8000/api/v1/"
            "notifications/test-webhook/"
            "success/token"
        )
    )

    assert destination.startswith(
        "http://api:8000/"
    )


def test_unlisted_webhook_host_is_blocked() -> None:
    with pytest.raises(
        ValueError
    ):
        normalize_webhook_destination(
            "https://unlisted.example/webhook"
        )


def test_email_destination_is_normalized() -> None:
    assert normalize_email_destination(
        "  AP@Example.test  "
    ) == "ap@example.test"


def test_invalid_email_destination_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        normalize_email_destination(
            "not-an-email"
        )


def test_retry_delay_is_exponential_and_capped(
    monkeypatch,
) -> None:
    from app.services.notifications import (
        providers,
    )

    monkeypatch.setattr(
        providers.settings,
        "notification_retry_base_seconds",
        2,
    )

    monkeypatch.setattr(
        providers.settings,
        "notification_retry_max_seconds",
        5,
    )

    assert retry_delay_seconds(
        attempt_number=1
    ) == 2

    assert retry_delay_seconds(
        attempt_number=2
    ) == 4

    assert retry_delay_seconds(
        attempt_number=3
    ) == 5


def test_retryable_webhook_statuses() -> None:
    assert webhook_status_is_retryable(
        429
    )

    assert webhook_status_is_retryable(
        503
    )

    assert not webhook_status_is_retryable(
        400
    )


def test_notification_payload_preserves_export() -> None:
    payload = _notification_payload(
        ready_export()
    )

    assert (
        payload["event"]
        == "accounting.export.ready"
    )

    assert (
        payload["export"]["id"]
        == ready_export()["id"]
    )

    assert (
        payload["accounting_payload"][
            "invoice"
        ]["header"][
            "invoice_number"
        ]
        == "INV-1001"
    )
