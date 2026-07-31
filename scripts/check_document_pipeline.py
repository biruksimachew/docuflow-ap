import io
import time
from uuid import uuid4

import httpx
from PIL import ImageDraw

from tests.ocr_test_image import (
    create_test_invoice_image,
)


def create_unique_invoice_png() -> bytes:
    image = create_test_invoice_image()

    draw = ImageDraw.Draw(image)

    draw.text(
        (1050, 930),
        f"Processing run {uuid4()}",
        fill="black",
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
        "http://127.0.0.1:8000/api/v1/documents/upload",
        files={
            "file": (
                "Meridian OCR Pipeline Invoice.png",
                create_unique_invoice_png(),
                "image/png",
            )
        },
        data={
            "source_channel": "WEB_UPLOAD",
        },
        timeout=30,
    )

    upload_response.raise_for_status()

    upload_payload = upload_response.json()

    assert upload_response.status_code == 201
    assert upload_payload["status"] == "RECEIVED"
    assert upload_payload["is_duplicate"] is False
    assert upload_payload["processing_enqueued"] is True
    assert upload_payload["processing_task_id"]

    document_id = upload_payload["document_id"]

    snapshot = None

    for _ in range(60):
        response = httpx.get(
            (
                "http://127.0.0.1:8000"
                f"/api/v1/documents/{document_id}/processing"
            ),
            timeout=20,
        )

        response.raise_for_status()
        snapshot = response.json()

        document_status = snapshot["document"]["status"]

        if document_status in {
            "REVIEW_REQUIRED",
            "FAILED",
        }:
            break

        time.sleep(2)

    if snapshot is None:
        raise RuntimeError(
            "No processing snapshot was returned."
        )

    document = snapshot["document"]

    if document["status"] == "FAILED":
        raise RuntimeError(
            {
                "error_code": document["last_error_code"],
                "error_message": document["last_error_message"],
            }
        )

    assert document["status"] == "REVIEW_REQUIRED"
    assert document["processing_attempts"] == 1

    processing_run = snapshot[
        "latest_processing_run"
    ]

    assert processing_run is not None
    assert processing_run["status"] == "SUCCEEDED"

    pages = snapshot["pages"]

    assert len(pages) == 1
    assert pages[0]["page_number"] == 1
    assert pages[0]["preprocessing_operations"]

    ocr_run = snapshot["ocr_run"]

    assert ocr_run is not None
    assert ocr_run["status"] == "SUCCEEDED"
    assert ocr_run["provider"] == "tesseract"

    results = snapshot["ocr_page_results"]

    assert len(results) == 1

    normalized_text = results[0][
        "raw_text"
    ].upper()

    assert "INVOICE" in normalized_text
    assert "INV-1001" in normalized_text
    assert "138.00" in normalized_text

    assert results[0]["average_confidence"] is not None
    assert results[0]["tokens"]

    elapsed_seconds = round(
        time.monotonic() - started_at,
        2,
    )

    print(
        {
            "status": "passed",
            "document_id": document_id,
            "processing_status": document["status"],
            "processing_run_status": processing_run["status"],
            "ocr_run_status": ocr_run["status"],
            "provider": ocr_run["provider"],
            "page_count": len(pages),
            "token_count": len(results[0]["tokens"]),
            "detected_invoice_number": "INV-1001",
            "detected_total": "138.00",
            "elapsed_seconds": elapsed_seconds,
        }
    )


if __name__ == "__main__":
    main()