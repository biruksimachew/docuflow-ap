from __future__ import annotations

import time
from uuid import uuid4

import httpx

from scripts.auth_test_tokens import (
    authenticated_get,
    authorization_headers,
)
from scripts.check_accounting_exports import (
    generate_export,
    upload_and_wait,
)


BASE_URL = "http://127.0.0.1:8000"


def create_delivery(
    *,
    export_id: str,
    channel: str,
    destination: str,
) -> httpx.Response:
    return httpx.post(
        (
            f"{BASE_URL}/api/v1/exports/"
            f"{export_id}/notifications"
        ),
        headers=authorization_headers(
            "AP_CLERK"
        ),
        json={
            "channel": channel,
            "destination": destination,
        },
        timeout=30,
    )


def wait_for_delivery(
    delivery_id: str,
    *,
    timeout_seconds: int = 60,
) -> dict:
    deadline = (
        time.monotonic()
        + timeout_seconds
    )

    latest = None

    while time.monotonic() < deadline:
        response = authenticated_get(
            (
                f"{BASE_URL}/api/v1/"
                f"notifications/{delivery_id}"
            ),
            role="ADMIN",
            timeout=20,
        )

        response.raise_for_status()

        latest = response.json()

        current_status = latest[
            "delivery"
        ]["status"]

        if current_status in {
            "SUCCEEDED",
            "FAILED",
        }:
            return latest

        time.sleep(1)

    raise RuntimeError(
        "Notification delivery did not reach a final state. "
        f"Latest snapshot: {latest}"
    )


def create_approved_export_fixture(
    *,
    max_attempts: int = 3,
) -> tuple[str, str, str]:
    observed_attempts: list[dict] = []

    for attempt_number in range(
        1,
        max_attempts + 1,
    ):
        invoice_number = (
            "NTF-"
            f"{uuid4().int % 100000000:08d}"
        )

        document_id, document_status = (
            upload_and_wait(
                invoice_number=invoice_number,
                purchase_order_number=(
                    "PO-7001"
                ),
            )
        )

        observed_attempts.append(
            {
                "attempt_number": (
                    attempt_number
                ),
                "invoice_number": (
                    invoice_number
                ),
                "document_id": document_id,
                "document_status": (
                    document_status
                ),
            }
        )

        if (
            document_status
            != "AUTO_APPROVED"
        ):
            print(
                {
                    "fixture_attempt": (
                        attempt_number
                    ),
                    "invoice_number": (
                        invoice_number
                    ),
                    "document_id": (
                        document_id
                    ),
                    "document_status": (
                        document_status
                    ),
                    "action": (
                        "retrying_fixture"
                    ),
                }
            )

            continue

        export_response = generate_export(
            document_id=document_id,
            export_format="JSON",
        )

        export_response.raise_for_status()

        export_id = export_response.json()[
            "export"
        ]["id"]

        return (
            document_id,
            document_status,
            export_id,
        )

    raise RuntimeError(
        "Could not create an AUTO_APPROVED notification "
        "test fixture after "
        f"{max_attempts} attempts. "
        f"Observed attempts: {observed_attempts}"
    )


def main() -> None:
    started_at = time.monotonic()

    (
        document_id,
        document_status,
        export_id,
    ) = create_approved_export_fixture()

    success_token = uuid4().hex

    success_destination = (
        "http://api:8000/api/v1/"
        "notifications/test-webhook/"
        f"success/{success_token}"
    )

    webhook_response = create_delivery(
        export_id=export_id,
        channel="WEBHOOK",
        destination=success_destination,
    )

    webhook_response.raise_for_status()

    webhook_payload = (
        webhook_response.json()
    )

    assert (
        webhook_payload["status"]
        == "queued"
    )

    webhook_delivery_id = (
        webhook_payload["delivery"]["id"]
    )

    webhook_snapshot = wait_for_delivery(
        webhook_delivery_id
    )

    assert (
        webhook_snapshot["delivery"][
            "status"
        ]
        == "SUCCEEDED"
    )

    assert (
        webhook_snapshot["delivery"][
            "attempt_count"
        ]
        == 1
    )

    assert len(
        webhook_snapshot["attempts"]
    ) == 1

    assert (
        webhook_snapshot["attempts"][0][
            "status"
        ]
        == "SUCCEEDED"
    )

    reused_response = create_delivery(
        export_id=export_id,
        channel="WEBHOOK",
        destination=success_destination,
    )

    reused_response.raise_for_status()

    reused_payload = (
        reused_response.json()
    )

    assert (
        reused_payload["status"]
        == "reused"
    )

    assert (
        reused_payload["delivery"]["id"]
        == webhook_delivery_id
    )

    retry_token = uuid4().hex

    retry_destination = (
        "http://api:8000/api/v1/"
        "notifications/test-webhook/"
        f"fail-once/{retry_token}"
    )

    retry_response = create_delivery(
        export_id=export_id,
        channel="WEBHOOK",
        destination=retry_destination,
    )

    retry_response.raise_for_status()

    retry_delivery_id = (
        retry_response.json()[
            "delivery"
        ]["id"]
    )

    retry_snapshot = wait_for_delivery(
        retry_delivery_id,
        timeout_seconds=90,
    )

    assert (
        retry_snapshot["delivery"][
            "status"
        ]
        == "SUCCEEDED"
    )

    assert (
        retry_snapshot["delivery"][
            "attempt_count"
        ]
        == 2
    )

    retry_attempt_statuses = [
        attempt["status"]
        for attempt in (
            retry_snapshot["attempts"]
        )
    ]

    assert retry_attempt_statuses == [
        "FAILED",
        "SUCCEEDED",
    ]

    assert (
        retry_snapshot["attempts"][0][
            "retryable"
        ]
        is True
    )

    email_destination = (
        "ap-team@example.test"
    )

    email_response = create_delivery(
        export_id=export_id,
        channel="EMAIL",
        destination=email_destination,
    )

    email_response.raise_for_status()

    email_delivery_id = (
        email_response.json()[
            "delivery"
        ]["id"]
    )

    email_snapshot = wait_for_delivery(
        email_delivery_id
    )

    assert (
        email_snapshot["delivery"][
            "status"
        ]
        == "SUCCEEDED"
    )

    assert (
        email_snapshot["delivery"][
            "provider"
        ]
        == "EMAIL_LOCAL_SINK"
    )

    local_email = email_snapshot[
        "local_email_message"
    ]

    assert local_email is not None

    assert (
        local_email["recipient"]
        == email_destination
    )

    assert export_id in (
        local_email["body_text"]
    )

    blocked_destination = (
        "https://unlisted.example/webhook"
    )

    blocked_response = create_delivery(
        export_id=export_id,
        channel="WEBHOOK",
        destination=blocked_destination,
    )

    assert (
        blocked_response.status_code
        == 422
    )

    deliveries_response = authenticated_get(
        (
            f"{BASE_URL}/api/v1/exports/"
            f"{export_id}/notifications"
        ),
        role="ADMIN",
        timeout=20,
    )

    deliveries_response.raise_for_status()

    assert (
        deliveries_response.json()[
            "count"
        ]
        == 3
    )

    elapsed_seconds = round(
        time.monotonic()
        - started_at,
        2,
    )

    print(
        {
            "status": "passed",
            "document_id": document_id,
            "document_status": (
                document_status
            ),
            "export_id": export_id,
            "webhook_delivery_id": (
                webhook_delivery_id
            ),
            "webhook_succeeded": True,
            "webhook_idempotent_reuse": (
                True
            ),
            "retry_delivery_id": (
                retry_delivery_id
            ),
            "retry_attempt_statuses": (
                retry_attempt_statuses
            ),
            "exponential_retry_succeeded": (
                True
            ),
            "email_delivery_id": (
                email_delivery_id
            ),
            "email_local_sink_succeeded": (
                True
            ),
            "destination_allowlist_enforced": (
                True
            ),
            "immutable_attempt_count": (
                len(
                    webhook_snapshot[
                        "attempts"
                    ]
                )
                + len(
                    retry_snapshot[
                        "attempts"
                    ]
                )
                + len(
                    email_snapshot[
                        "attempts"
                    ]
                )
            ),
            "elapsed_seconds": (
                elapsed_seconds
            ),
        }
    )


if __name__ == "__main__":
    main()
