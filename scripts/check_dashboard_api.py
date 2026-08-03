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


def create_dashboard_invoice() -> tuple[str, str]:
    invoice_number = (
        "DASH-"
        f"{uuid4().int % 100000000:08d}"
    )

    image = create_line_item_invoice_image(
        invoice_number=invoice_number,
        purchase_order_number="PO-7001",
        marker="Dashboard API fixture",
    )

    buffer = io.BytesIO()
    image.save(
        buffer,
        format="PNG",
    )

    upload = httpx.post(
        (
            f"{BASE_URL}"
            "/api/v1/documents/upload"
        ),
        files={
            "file": (
                f"{invoice_number}.png",
                buffer.getvalue(),
                "image/png",
            )
        },
        data={
            "source_channel": "WEB_UPLOAD",
        },
        timeout=30,
    )
    upload.raise_for_status()

    document_id = upload.json()[
        "document_id"
    ]

    terminal_status = None

    for _ in range(60):
        snapshot = authenticated_get(
            (
                f"{BASE_URL}/api/v1/documents/"
                f"{document_id}/processing"
            ),
            role="AP_CLERK",
            timeout=20,
        )
        snapshot.raise_for_status()

        terminal_status = snapshot.json()[
            "document"
        ]["status"]

        if terminal_status in {
            "AUTO_APPROVED",
            "REVIEW_REQUIRED",
            "REJECTED",
            "FAILED",
        }:
            break

        time.sleep(2)

    if terminal_status is None:
        raise RuntimeError(
            "Dashboard fixture did not reach a terminal state."
        )

    return document_id, terminal_status


def main() -> None:
    started_at = time.monotonic()

    document_id, terminal_status = (
        create_dashboard_invoice()
    )

    overview = authenticated_get(
        (
            f"{BASE_URL}"
            "/api/v1/dashboard/overview"
        ),
        role="AP_CLERK",
        timeout=20,
    )
    overview.raise_for_status()

    overview_payload = overview.json()

    assert (
        overview_payload["metrics"][
            "total_documents"
        ]
        >= 1
    )

    documents = authenticated_get(
        (
            f"{BASE_URL}"
            "/api/v1/dashboard/documents"
            "?limit=100"
        ),
        role="AP_CLERK",
        timeout=20,
    )
    documents.raise_for_status()

    document_rows = documents.json()[
        "documents"
    ]

    matching_rows = [
        row
        for row in document_rows
        if row["id"] == document_id
    ]

    assert len(matching_rows) == 1

    detail = authenticated_get(
        (
            f"{BASE_URL}"
            "/api/v1/dashboard/documents/"
            f"{document_id}"
        ),
        role="AP_CLERK",
        timeout=20,
    )
    detail.raise_for_status()

    assert (
        detail.json()["document"]["id"]
        == document_id
    )

    clerk_reviews = authenticated_get(
        (
            f"{BASE_URL}"
            "/api/v1/dashboard/reviews"
        ),
        role="AP_CLERK",
        timeout=20,
    )

    assert clerk_reviews.status_code == 403

    admin_reviews = authenticated_get(
        (
            f"{BASE_URL}"
            "/api/v1/dashboard/reviews"
        ),
        role="ADMIN",
        timeout=20,
    )
    admin_reviews.raise_for_status()

    elapsed_seconds = round(
        time.monotonic()
        - started_at,
        2,
    )

    print(
        {
            "status": "passed",
            "document_id": document_id,
            "document_status": terminal_status,
            "overview_total_documents": (
                overview_payload["metrics"][
                    "total_documents"
                ]
            ),
            "document_visible_in_queue": True,
            "document_detail_available": True,
            "clerk_review_queue_denied": True,
            "admin_review_queue_available": True,
            "elapsed_seconds": elapsed_seconds,
        }
    )


if __name__ == "__main__":
    main()
