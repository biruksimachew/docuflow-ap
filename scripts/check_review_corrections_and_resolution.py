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


def invoice_png(
    invoice_number: str,
) -> bytes:
    image = create_line_item_invoice_image(
        invoice_number=invoice_number,
        purchase_order_number=None,
        marker=f"Review resolution {uuid4()}",
    )

    buffer = io.BytesIO()

    image.save(
        buffer,
        format="PNG",
    )

    return buffer.getvalue()


def create_review_document(
    invoice_number: str,
) -> tuple[str, str]:
    upload = httpx.post(
        (
            f"{BASE_URL}"
            "/api/v1/documents/upload"
        ),
        files={
            "file": (
                f"{invoice_number}.png",
                invoice_png(
                    invoice_number
                ),
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

    status = None

    for _ in range(60):
        response = authenticated_get(
            (
                f"{BASE_URL}/api/v1/documents/"
                f"{document_id}/processing"
            ),
            role="REVIEWER",
            timeout=20,
        )

        response.raise_for_status()

        status = response.json()[
            "document"
        ]["status"]

        if status in {
            "AUTO_APPROVED",
            "REVIEW_REQUIRED",
            "REJECTED",
            "FAILED",
        }:
            break

        time.sleep(2)

    assert status == "REVIEW_REQUIRED"

    queue = authenticated_get(
        (
            f"{BASE_URL}/api/v1/reviews"
            f"?status=OPEN"
            f"&document_id={document_id}"
        ),
        role="REVIEWER",
        timeout=20,
    )

    queue.raise_for_status()

    payload = queue.json()

    assert payload["count"] == 1

    return (
        document_id,
        payload["cases"][0]["id"],
    )


def claim_case(
    review_case_id: str,
    *,
    role: str,
) -> None:
    response = httpx.post(
        (
            f"{BASE_URL}/api/v1/reviews/"
            f"{review_case_id}/claim"
        ),
        headers=authorization_headers(
            role
        ),
        timeout=20,
    )

    response.raise_for_status()


def main() -> None:
    started_at = time.monotonic()

    approved_document_id, approved_case_id = (
        create_review_document(
            f"CORR-{uuid4().hex[:8].upper()}"
        )
    )

    proposed = httpx.post(
        (
            f"{BASE_URL}/api/v1/reviews/"
            f"{approved_case_id}/corrections"
        ),
        headers=authorization_headers(
            "AP_CLERK"
        ),
        json={
            "target_type": "HEADER",
            "line_item_id": None,
            "field_name": (
                "purchase_order_number"
            ),
            "corrected_value": (
                "PO-7001"
            ),
            "reason": (
                "Verified against the procurement "
                "purchase-order register."
            ),
            "apply_immediately": False,
        },
        timeout=20,
    )

    proposed.raise_for_status()

    proposed_payload = proposed.json()

    correction_id = proposed_payload[
        "correction"
    ]["id"]

    assert (
        proposed_payload[
            "correction"
        ]["status"]
        == "PROPOSED"
    )

    clerk_resolution_attempt = httpx.post(
        (
            f"{BASE_URL}/api/v1/reviews/"
            f"{approved_case_id}/resolve"
        ),
        headers=authorization_headers(
            "AP_CLERK"
        ),
        json={
            "resolution": "APPROVE",
            "note": (
                "Attempted clerk approval must be denied."
            ),
        },
        timeout=20,
    )

    assert (
        clerk_resolution_attempt.status_code
        == 403
    )

    claim_case(
        approved_case_id,
        role="REVIEWER",
    )

    applied = httpx.post(
        (
            f"{BASE_URL}/api/v1/reviews/"
            f"{approved_case_id}/corrections/"
            f"{correction_id}/apply"
        ),
        headers=authorization_headers(
            "REVIEWER"
        ),
        timeout=60,
    )

    applied.raise_for_status()

    applied_payload = applied.json()

    assert (
        applied_payload[
            "correction"
        ]["status"]
        == "APPLIED"
    )

    control_run = applied_payload[
        "control_run"
    ]

    assert (
        control_run["status"]
        == "SUCCEEDED"
    )

    assert (
        control_run["outcome"]
        == "PASSED"
    )

    assert (
        control_run[
            "validation_passed"
        ]
        is True
    )

    assert (
        control_run[
            "duplicate_outcome"
        ]
        == "CLEAR"
    )

    assert (
        control_run[
            "vendor_outcome"
        ]
        == "MATCHED"
    )

    assert (
        control_run["po_outcome"]
        == "MATCHED"
    )

    effective = authenticated_get(
        (
            f"{BASE_URL}/api/v1/reviews/"
            f"{approved_case_id}"
            "/effective-invoice"
        ),
        role="REVIEWER",
        timeout=20,
    )

    effective.raise_for_status()

    effective_payload = effective.json()

    assert (
        effective_payload[
            "original"
        ]["header"][
            "purchase_order_number"
        ]
        is None
    )

    assert (
        effective_payload[
            "effective"
        ]["header"][
            "purchase_order_number"
        ]
        == "PO-7001"
    )

    approved = httpx.post(
        (
            f"{BASE_URL}/api/v1/reviews/"
            f"{approved_case_id}/resolve"
        ),
        headers=authorization_headers(
            "REVIEWER"
        ),
        json={
            "resolution": "APPROVE",
            "note": (
                "Purchase order verified and all corrected "
                "controls passed successfully."
            ),
        },
        timeout=20,
    )

    approved.raise_for_status()

    approved_payload = approved.json()

    assert (
        approved_payload[
            "review_case"
        ]["status"]
        == "RESOLVED_APPROVED"
    )

    assert (
        approved_payload[
            "document"
        ]["status"]
        == "AUTO_APPROVED"
    )

    assert (
        approved_payload[
            "document"
        ]["final_resolution_source"]
        == "MANUAL"
    )

    rejected_document_id, rejected_case_id = (
        create_review_document(
            f"REJ-{uuid4().hex[:8].upper()}"
        )
    )

    claim_case(
        rejected_case_id,
        role="ADMIN",
    )

    rejected = httpx.post(
        (
            f"{BASE_URL}/api/v1/reviews/"
            f"{rejected_case_id}/resolve"
        ),
        headers=authorization_headers(
            "ADMIN"
        ),
        json={
            "resolution": "REJECT",
            "note": (
                "Invoice rejected because no authorized "
                "purchase order could be confirmed."
            ),
        },
        timeout=20,
    )

    rejected.raise_for_status()

    rejected_payload = rejected.json()

    assert (
        rejected_payload[
            "review_case"
        ]["status"]
        == "RESOLVED_REJECTED"
    )

    assert (
        rejected_payload[
            "document"
        ]["status"]
        == "REJECTED"
    )

    case_snapshot = authenticated_get(
        (
            f"{BASE_URL}/api/v1/reviews/"
            f"{approved_case_id}"
        ),
        role="ADMIN",
        timeout=20,
    )

    case_snapshot.raise_for_status()

    snapshot = case_snapshot.json()

    event_types = [
        event["event_type"]
        for event in snapshot["events"]
    ]

    assert (
        "CORRECTION_PROPOSED"
        in event_types
    )

    assert (
        "CORRECTION_APPLIED"
        in event_types
    )

    assert (
        "CONTROLS_RERUN"
        in event_types
    )

    assert (
        "RESOLVED_APPROVED"
        in event_types
    )

    elapsed_seconds = round(
        time.monotonic()
        - started_at,
        2,
    )

    print(
        {
            "status": "passed",
            "approved_document_id": (
                approved_document_id
            ),
            "approved_case_id": (
                approved_case_id
            ),
            "correction_status": (
                "APPLIED"
            ),
            "original_po_preserved": True,
            "effective_po_number": (
                "PO-7001"
            ),
            "control_outcome": (
                control_run["outcome"]
            ),
            "validation_passed": True,
            "duplicate_outcome": (
                control_run[
                    "duplicate_outcome"
                ]
            ),
            "vendor_outcome": (
                control_run[
                    "vendor_outcome"
                ]
            ),
            "po_outcome": (
                control_run[
                    "po_outcome"
                ]
            ),
            "approved_case_status": (
                approved_payload[
                    "review_case"
                ]["status"]
            ),
            "approved_document_status": (
                approved_payload[
                    "document"
                ]["status"]
            ),
            "rejected_document_id": (
                rejected_document_id
            ),
            "rejected_case_status": (
                rejected_payload[
                    "review_case"
                ]["status"]
            ),
            "clerk_resolution_denied": True,
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