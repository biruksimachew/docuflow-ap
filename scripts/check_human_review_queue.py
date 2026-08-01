from __future__ import annotations

import io
import time
from uuid import uuid4

import httpx

from scripts.auth_test_tokens import (
    authenticated_get,
    authorization_headers,
)
from tests.line_item_test_image import (
    create_line_item_invoice_image,
)


BASE_URL = "http://127.0.0.1:8000"


def create_review_invoice() -> bytes:
    invoice_number = (
        f"QUEUE-{uuid4().hex[:8].upper()}"
    )

    image = create_line_item_invoice_image(
        invoice_number=invoice_number,
        purchase_order_number=None,
        marker=f"Review queue {uuid4()}",
    )

    buffer = io.BytesIO()

    image.save(
        buffer,
        format="PNG",
    )

    return buffer.getvalue()


def main() -> None:
    started_at = time.monotonic()

    upload_response = httpx.post(
        (
            f"{BASE_URL}"
            "/api/v1/documents/upload"
        ),
        files={
            "file": (
                "Review Queue Invoice.png",
                create_review_invoice(),
                "image/png",
            )
        },
        data={
            "source_channel": "WEB_UPLOAD",
        },
        timeout=30,
    )

    upload_response.raise_for_status()

    document_id = upload_response.json()[
        "document_id"
    ]

    document_status = None

    for _ in range(60):
        processing_response = authenticated_get(
            (
                f"{BASE_URL}/api/v1/documents/"
                f"{document_id}/processing"
            ),
            role="REVIEWER",
            timeout=20,
        )

        processing_response.raise_for_status()

        document_status = (
            processing_response.json()[
                "document"
            ]["status"]
        )

        if document_status in {
            "AUTO_APPROVED",
            "REVIEW_REQUIRED",
            "REJECTED",
            "FAILED",
        }:
            break

        time.sleep(2)

    assert (
        document_status
        == "REVIEW_REQUIRED"
    )

    queue_response = authenticated_get(
        (
            f"{BASE_URL}/api/v1/reviews"
            f"?status=OPEN"
            f"&document_id={document_id}"
        ),
        role="REVIEWER",
        timeout=20,
    )

    queue_response.raise_for_status()

    queue_payload = queue_response.json()

    assert queue_payload["count"] == 1

    review_case = queue_payload[
        "cases"
    ][0]

    review_case_id = review_case["id"]

    assert review_case["status"] == "OPEN"

    assert (
        "PURCHASE_ORDER_NOT_PROVIDED"
        in review_case["reason_codes"]
    )

    clerk_claim = httpx.post(
        (
            f"{BASE_URL}/api/v1/reviews/"
            f"{review_case_id}/claim"
        ),
        headers=authorization_headers(
            "AP_CLERK"
        ),
        timeout=20,
    )

    assert clerk_claim.status_code == 403

    reviewer_claim = httpx.post(
        (
            f"{BASE_URL}/api/v1/reviews/"
            f"{review_case_id}/claim"
        ),
        headers=authorization_headers(
            "REVIEWER"
        ),
        timeout=20,
    )

    reviewer_claim.raise_for_status()

    claimed_case = reviewer_claim.json()[
        "review_case"
    ]

    assert claimed_case["status"] == "CLAIMED"

    assert (
        claimed_case["claimed_by_email"]
        == "reviewer@docuflow.local"
    )

    note_response = httpx.post(
        (
            f"{BASE_URL}/api/v1/reviews/"
            f"{review_case_id}/notes"
        ),
        headers=authorization_headers(
            "REVIEWER"
        ),
        json={
            "note": (
                "PO reference is missing. "
                "Contact procurement before resolution."
            )
        },
        timeout=20,
    )

    note_response.raise_for_status()

    assert (
        note_response.json()["status"]
        == "note_added"
    )

    release_response = httpx.post(
        (
            f"{BASE_URL}/api/v1/reviews/"
            f"{review_case_id}/release"
        ),
        headers=authorization_headers(
            "REVIEWER"
        ),
        timeout=20,
    )

    release_response.raise_for_status()

    released_case = release_response.json()[
        "review_case"
    ]

    assert released_case["status"] == "OPEN"

    snapshot_response = authenticated_get(
        (
            f"{BASE_URL}/api/v1/reviews/"
            f"{review_case_id}"
        ),
        role="ADMIN",
        timeout=20,
    )

    snapshot_response.raise_for_status()

    snapshot = snapshot_response.json()

    event_types = [
        event["event_type"]
        for event in snapshot["events"]
    ]

    assert "CREATED" in event_types
    assert "CLAIMED" in event_types
    assert "NOTE_ADDED" in event_types
    assert "RELEASED" in event_types

    elapsed_seconds = round(
        time.monotonic()
        - started_at,
        2,
    )

    print(
        {
            "status": "passed",
            "document_id": document_id,
            "document_status": document_status,
            "review_case_id": review_case_id,
            "initial_case_status": "OPEN",
            "claimed_case_status": "CLAIMED",
            "released_case_status": (
                released_case["status"]
            ),
            "clerk_claim_denied": True,
            "reviewer_claim_allowed": True,
            "review_note_preserved": True,
            "immutable_event_types": (
                event_types
            ),
            "elapsed_seconds": (
                elapsed_seconds
            ),
        }
    )


if __name__ == "__main__":
    main()