import io
import time
from uuid import uuid4

import httpx

from scripts.auth_test_tokens import (
    authenticated_get,
)

from tests.line_item_test_image import (
    create_line_item_invoice_image,
)


BASE_URL = "http://127.0.0.1:8000"


def create_invoice_png(
    invoice_number: str,
) -> bytes:
    image = create_line_item_invoice_image(
        invoice_number=invoice_number,
        purchase_order_number="PO-7001",
        marker=f"Matching run {uuid4()}",
    )

    buffer = io.BytesIO()

    image.save(
        buffer,
        format="PNG",
    )

    return buffer.getvalue()


def main() -> None:
    started_at = time.monotonic()

    invoice_number = (
        f"MATCH-{uuid4().hex[:8].upper()}"
    )

    upload_response = httpx.post(
        (
            f"{BASE_URL}"
            "/api/v1/documents/upload"
        ),
        files={
            "file": (
                "Meridian Matched PO Invoice.png",
                create_invoice_png(
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

    upload_response.raise_for_status()

    payload = upload_response.json()

    assert upload_response.status_code == 201
    assert (
        payload["processing_enqueued"]
        is True
    )

    document_id = payload[
        "document_id"
    ]

    processing_snapshot = None

    for _ in range(60):
        response = authenticated_get(
            (
                f"{BASE_URL}/api/v1/documents/"
                f"{document_id}/processing"
            ),
            timeout=20,
        )

        response.raise_for_status()

        processing_snapshot = (
            response.json()
        )

        status = processing_snapshot[
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

    if processing_snapshot is None:
        raise RuntimeError(
            "No processing snapshot was returned."
        )

    document = processing_snapshot[
        "document"
    ]

    if document["status"] == "FAILED":
        raise RuntimeError(
            {
                "error_code": document[
                    "last_error_code"
                ],
                "error_message": document[
                    "last_error_message"
                ],
            }
        )

    assert (
        document["status"]
        == "AUTO_APPROVED"
    )

    matching_response = authenticated_get(
        (
            f"{BASE_URL}/api/v1/documents/"
            f"{document_id}/matching"
        ),
        timeout=20,
    )

    matching_response.raise_for_status()

    snapshot = matching_response.json()

    vendor_match = snapshot[
        "vendor_match"
    ]

    po_match = snapshot[
        "purchase_order_match"
    ]

    assert vendor_match is not None
    assert po_match is not None

    assert (
        vendor_match["status"]
        == "SUCCEEDED"
    )

    assert (
        vendor_match["ruleset_version"]
        == "vendor-identity-v1"
    )

    assert (
        vendor_match["outcome"]
        == "MATCHED"
    )

    assert (
        vendor_match["blocking"]
        is False
    )

    assert (
        vendor_match["matched_vendor_id"]
        == "10000000-0000-0000-0000-000000000001"
    )

    assert (
        vendor_match["candidate_count"]
        == 1
    )

    assert (
        po_match["status"]
        == "SUCCEEDED"
    )

    assert (
        po_match["ruleset_version"]
        == "purchase-order-v1"
    )

    assert (
        po_match["outcome"]
        == "MATCHED"
    )

    assert (
        po_match["blocking"]
        is False
    )

    assert (
        po_match[
            "matched_purchase_order_id"
        ]
        == "20000000-0000-0000-0000-000000000001"
    )

    assert (
        po_match["matched_line_count"]
        == 2
    )

    assert (
        po_match["mismatched_line_count"]
        == 0
    )

    checks = po_match[
        "check_results"
    ]

    assert (
        checks[
            "purchase_order_status_open"
        ]
        is True
    )

    assert (
        checks["vendor_matches"]
        is True
    )

    assert (
        checks["currency_matches"]
        is True
    )

    assert (
        checks["subtotal"]["matches"]
        is True
    )

    assert (
        checks["tax_amount"]["matches"]
        is True
    )

    assert (
        checks["total_amount"]["matches"]
        is True
    )

    assert (
        checks["line_items_match"]
        is True
    )

    assert len(
        checks["line_results"]
    ) == 2

    elapsed_seconds = round(
        time.monotonic()
        - started_at,
        2,
    )

    print(
        {
            "status": "passed",
            "document_id": document_id,
            "invoice_number": invoice_number,
            "document_status": (
                document["status"]
            ),
            "vendor_outcome": (
                vendor_match["outcome"]
            ),
            "vendor_code": (
                snapshot[
                    "vendor_candidates"
                ][0]["vendor_code"]
            ),
            "po_outcome": (
                po_match["outcome"]
            ),
            "po_number": (
                po_match["input_po_number"]
            ),
            "matched_line_count": (
                po_match[
                    "matched_line_count"
                ]
            ),
            "header_checks_passed": True,
            "line_checks_passed": True,
            "matching_evidence_preserved": True,
            "elapsed_seconds": (
                elapsed_seconds
            ),
        }
    )


if __name__ == "__main__":
    main()