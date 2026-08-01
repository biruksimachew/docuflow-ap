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

TERMINAL_STATUSES = {
    "AUTO_APPROVED",
    "REVIEW_REQUIRED",
    "REJECTED",
    "FAILED",
}


def create_invoice_png(
    *,
    invoice_number: str,
    purchase_order_number: str | None,
    marker: str,
) -> bytes:
    image = create_line_item_invoice_image(
        invoice_number=invoice_number,
        purchase_order_number=(
            purchase_order_number
        ),
        marker=marker,
    )

    buffer = io.BytesIO()

    image.save(
        buffer,
        format="PNG",
    )

    return buffer.getvalue()


def upload_invoice(
    *,
    invoice_number: str,
    purchase_order_number: str | None,
    marker: str,
    filename: str,
) -> str:
    response = httpx.post(
        (
            f"{BASE_URL}"
            "/api/v1/documents/upload"
        ),
        files={
            "file": (
                filename,
                create_invoice_png(
                    invoice_number=(
                        invoice_number
                    ),
                    purchase_order_number=(
                        purchase_order_number
                    ),
                    marker=marker,
                ),
                "image/png",
            )
        },
        data={
            "source_channel": "WEB_UPLOAD",
        },
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    assert response.status_code == 201

    assert (
        payload["processing_enqueued"]
        is True
    )

    return payload[
        "document_id"
    ]


def wait_for_terminal_status(
    document_id: str,
) -> dict:
    for _ in range(60):
        response = authenticated_get(
            (
                f"{BASE_URL}/api/v1/documents/"
                f"{document_id}/processing"
            ),
            timeout=20,
        )

        response.raise_for_status()

        snapshot = response.json()

        status = snapshot[
            "document"
        ]["status"]

        if status in TERMINAL_STATUSES:
            if status == "FAILED":
                raise RuntimeError(
                    {
                        "document_id": (
                            document_id
                        ),
                        "error_code": (
                            snapshot["document"][
                                "last_error_code"
                            ]
                        ),
                        "error_message": (
                            snapshot["document"][
                                "last_error_message"
                            ]
                        ),
                    }
                )

            return snapshot

        time.sleep(2)

    raise TimeoutError(
        "Document decision did not complete."
    )


def get_decision(
    document_id: str,
) -> dict:
    response = authenticated_get(
        (
            f"{BASE_URL}/api/v1/documents/"
            f"{document_id}/decision"
        ),
        timeout=20,
    )

    response.raise_for_status()

    snapshot = response.json()

    decision_run = snapshot[
        "decision_run"
    ]

    assert decision_run is not None
    assert decision_run["status"] == "SUCCEEDED"
    assert (
        decision_run["policy_version"]
        == "invoice-decision-v1"
    )

    return snapshot


def main() -> None:
    started_at = time.monotonic()

    approved_invoice_number = (
        f"APP-{uuid4().hex[:8].upper()}"
    )

    approved_document_id = upload_invoice(
        invoice_number=(
            approved_invoice_number
        ),
        purchase_order_number="PO-7001",
        marker=f"Approved {uuid4()}",
        filename="Approved Invoice.png",
    )

    approved_processing = (
        wait_for_terminal_status(
            approved_document_id
        )
    )

    assert (
        approved_processing[
            "document"
        ]["status"]
        == "AUTO_APPROVED"
    )

    approved_snapshot = get_decision(
        approved_document_id
    )

    approved_run = approved_snapshot[
        "decision_run"
    ]

    assert (
        approved_run["outcome"]
        == "AUTO_APPROVED"
    )

    assert (
        approved_run["blocking"]
        is False
    )

    assert (
        approved_run["reason_codes"]
        == ["ALL_CONTROLS_PASSED"]
    )

    duplicate_document_id = upload_invoice(
        invoice_number=(
            approved_invoice_number
        ),
        purchase_order_number="PO-7001",
        marker=f"Duplicate {uuid4()}",
        filename="Duplicate Invoice Rescan.png",
    )

    duplicate_processing = (
        wait_for_terminal_status(
            duplicate_document_id
        )
    )

    assert (
        duplicate_processing[
            "document"
        ]["status"]
        == "REJECTED"
    )

    duplicate_snapshot = get_decision(
        duplicate_document_id
    )

    duplicate_run = duplicate_snapshot[
        "decision_run"
    ]

    assert (
        duplicate_run["outcome"]
        == "REJECTED"
    )

    assert (
        duplicate_run["blocking"]
        is True
    )

    assert (
        duplicate_run["reason_codes"]
        == [
            "CONFIRMED_BUSINESS_DUPLICATE"
        ]
    )

    review_document_id = upload_invoice(
        invoice_number=(
            f"REV-{uuid4().hex[:8].upper()}"
        ),
        purchase_order_number=None,
        marker=f"Review {uuid4()}",
        filename="Invoice Without PO.png",
    )

    review_processing = (
        wait_for_terminal_status(
            review_document_id
        )
    )

    assert (
        review_processing[
            "document"
        ]["status"]
        == "REVIEW_REQUIRED"
    )

    review_snapshot = get_decision(
        review_document_id
    )

    review_run = review_snapshot[
        "decision_run"
    ]

    assert (
        review_run["outcome"]
        == "REVIEW_REQUIRED"
    )

    assert (
        review_run["blocking"]
        is True
    )

    assert (
        "PURCHASE_ORDER_NOT_PROVIDED"
        in review_run["reason_codes"]
    )

    assert (
        approved_run[
            "input_snapshot"
        ]["validation_outcome"]
        == "PASSED_CONTROLS"
    )

    assert (
        approved_run[
            "input_snapshot"
        ]["duplicate_outcome"]
        == "CLEAR"
    )

    assert (
        approved_run[
            "input_snapshot"
        ]["vendor_outcome"]
        == "MATCHED"
    )

    assert (
        approved_run[
            "input_snapshot"
        ]["po_outcome"]
        == "MATCHED"
    )

    assert (
        approved_run[
            "threshold_snapshot"
        ]["header_confidence_min"]
        == "0.90"
    )

    assert (
        approved_run[
            "threshold_snapshot"
        ]["line_item_confidence_min"]
        == "0.85"
    )

    elapsed_seconds = round(
        time.monotonic()
        - started_at,
        2,
    )

    print(
        {
            "status": "passed",
            "policy_version": (
                approved_run[
                    "policy_version"
                ]
            ),
            "approved_document_id": (
                approved_document_id
            ),
            "approved_outcome": (
                approved_run["outcome"]
            ),
            "duplicate_document_id": (
                duplicate_document_id
            ),
            "duplicate_outcome": (
                duplicate_run["outcome"]
            ),
            "review_document_id": (
                review_document_id
            ),
            "review_outcome": (
                review_run["outcome"]
            ),
            "approved_reason_codes": (
                approved_run[
                    "reason_codes"
                ]
            ),
            "rejected_reason_codes": (
                duplicate_run[
                    "reason_codes"
                ]
            ),
            "review_reason_codes": (
                review_run[
                    "reason_codes"
                ]
            ),
            "input_evidence_preserved": True,
            "threshold_evidence_preserved": True,
            "elapsed_seconds": (
                elapsed_seconds
            ),
        }
    )


if __name__ == "__main__":
    main()