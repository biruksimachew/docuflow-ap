import io
import time
from uuid import uuid4

import httpx

from tests.line_item_test_image import (
    create_line_item_invoice_image,
)


BASE_URL = "http://127.0.0.1:8000"


def create_invoice_png(
    *,
    invoice_number: str,
    marker: str,
) -> bytes:
    image = create_line_item_invoice_image(
        invoice_number=invoice_number,
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
    marker: str,
    filename: str,
) -> dict:
    response = httpx.post(
        f"{BASE_URL}/api/v1/documents/upload",
        files={
            "file": (
                filename,
                create_invoice_png(
                    invoice_number=(
                        invoice_number
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

    return payload


def wait_for_processing(
    document_id: str,
) -> dict:
    for _ in range(60):
        response = httpx.get(
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

        if status in {
            "REVIEW_REQUIRED",
            "FAILED",
        }:
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
        "Document processing did not complete."
    )


def get_duplicate_snapshot(
    document_id: str,
) -> dict:
    response = httpx.get(
        (
            f"{BASE_URL}/api/v1/documents/"
            f"{document_id}/duplicate-check"
        ),
        timeout=20,
    )

    response.raise_for_status()

    return response.json()


def main() -> None:
    started_at = time.monotonic()

    invoice_number = (
        f"DUP-{uuid4().hex[:8].upper()}"
    )

    first_upload = upload_invoice(
        invoice_number=invoice_number,
        marker=f"Original {uuid4()}",
        filename="Original Business Invoice.png",
    )

    first_document_id = first_upload[
        "document_id"
    ]

    wait_for_processing(
        first_document_id
    )

    first_snapshot = get_duplicate_snapshot(
        first_document_id
    )

    first_check = first_snapshot[
        "duplicate_check"
    ]

    assert first_check is not None

    assert (
        first_check["status"]
        == "SUCCEEDED"
    )

    assert (
        first_check["outcome"]
        == "CLEAR"
    )

    assert (
        first_check["blocking"]
        is False
    )

    assert (
        first_check["candidate_count"]
        == 0
    )

    second_upload = upload_invoice(
        invoice_number=invoice_number,
        marker=f"Rescanned {uuid4()}",
        filename="Rescanned Business Invoice.png",
    )

    second_document_id = second_upload[
        "document_id"
    ]

    assert (
        second_document_id
        != first_document_id
    )

    wait_for_processing(
        second_document_id
    )

    second_snapshot = get_duplicate_snapshot(
        second_document_id
    )

    second_check = second_snapshot[
        "duplicate_check"
    ]

    assert second_check is not None

    assert (
        second_check["status"]
        == "SUCCEEDED"
    )

    assert (
        second_check["ruleset_version"]
        == "business-duplicate-v1"
    )

    assert (
        second_check["outcome"]
        == "BUSINESS_DUPLICATE"
    )

    assert (
        second_check["blocking"]
        is True
    )

    assert (
        second_check["exact_match_count"]
        >= 1
    )

    assert (
        second_check["matched_document_id"]
        == first_document_id
    )

    candidates = second_snapshot[
        "candidates"
    ]

    assert candidates

    exact_candidate = next(
        candidate
        for candidate in candidates
        if candidate["outcome"]
        == "BUSINESS_DUPLICATE"
    )

    assert (
        exact_candidate[
            "candidate_document_id"
        ]
        == first_document_id
    )

    assert (
        exact_candidate["match_score"]
        == 1.0
    )

    field_matches = exact_candidate[
        "field_matches"
    ]

    assert all(
        field_matches[field_name]
        for field_name in (
            "vendor_name",
            "invoice_number",
            "invoice_date",
            "currency",
            "total_amount",
        )
    )

    elapsed_seconds = round(
        time.monotonic()
        - started_at,
        2,
    )

    print(
        {
            "status": "passed",
            "invoice_number": (
                invoice_number
            ),
            "original_document_id": (
                first_document_id
            ),
            "duplicate_document_id": (
                second_document_id
            ),
            "first_outcome": (
                first_check["outcome"]
            ),
            "second_outcome": (
                second_check["outcome"]
            ),
            "blocking": (
                second_check["blocking"]
            ),
            "match_score": (
                exact_candidate[
                    "match_score"
                ]
            ),
            "matched_fields": (
                field_matches
            ),
            "different_file_same_business_invoice_detected": True,
            "elapsed_seconds": (
                elapsed_seconds
            ),
        }
    )


if __name__ == "__main__":
    main()