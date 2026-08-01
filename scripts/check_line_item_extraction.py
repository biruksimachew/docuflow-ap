import io
import time
from uuid import uuid4

import httpx

from scripts.auth_test_tokens import (
    authenticated_get,
)
from PIL import ImageDraw

from tests.line_item_test_image import (
    create_line_item_invoice_image,
)


def create_unique_invoice_png() -> bytes:
    image = (
        create_line_item_invoice_image()
    )

    draw = ImageDraw.Draw(
        image
    )

    draw.text(
        (
            1050,
            1190,
        ),
        f"Line item run {uuid4()}",
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
        (
            "http://127.0.0.1:8000"
            "/api/v1/documents/upload"
        ),
        files={
            "file": (
                "Meridian Line Item Invoice.png",
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

    upload_payload = (
        upload_response.json()
    )

    assert upload_response.status_code == 201
    assert (
        upload_payload[
            "processing_enqueued"
        ]
        is True
    )

    document_id = upload_payload[
        "document_id"
    ]

    processing_snapshot = None

    for _ in range(60):
        response = authenticated_get(
            (
                "http://127.0.0.1:8000"
                f"/api/v1/documents/{document_id}"
                "/processing"
            ),
            timeout=20,
        )

        response.raise_for_status()

        processing_snapshot = response.json()

        document_status = (
            processing_snapshot[
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

    assert document["status"] in {
        "AUTO_APPROVED",
        "REVIEW_REQUIRED",
        "REJECTED",
    }

    line_response = authenticated_get(
        (
            "http://127.0.0.1:8000"
            f"/api/v1/documents/{document_id}"
            "/line-items"
        ),
        timeout=20,
    )

    line_response.raise_for_status()

    snapshot = line_response.json()

    extraction = snapshot[
        "invoice_extraction"
    ]

    assert extraction is not None
    assert extraction["status"] == "SUCCEEDED"
    assert extraction["line_item_count"] == 2
    assert extraction[
        "line_item_confidence"
    ] > 0.80

    items = snapshot[
        "line_items"
    ]

    assert len(items) == 2

    first = items[0]
    second = items[1]

    assert first["line_number"] == 1
    assert (
        first["description"]
        == "Printer Paper"
    )
    assert first["quantity"] == "2"
    assert first["unit_price"] == "50.00"
    assert first["line_total"] == "100.00"
    assert first["currency"] == "USD"

    assert second["line_number"] == 2
    assert (
        second["description"]
        == "Blue Pens"
    )
    assert second["quantity"] == "1"
    assert second["unit_price"] == "20.00"
    assert second["line_total"] == "20.00"
    assert second["currency"] == "USD"

    for item in items:
        assert item["confidence"] > 0
        assert item["page_number"] == 1
        assert item["raw_row_text"]
        assert item["extraction_method"]

        assert item[
            "normalized_values"
        ]

        assert item[
            "field_evidence"
        ]["quantity"][
            "raw_value"
        ]

        assert item[
            "field_evidence"
        ]["line_total"][
            "normalized_value"
        ]

        assert item[
            "row_evidence"
        ]["bounding_box"]

        assert item[
            "row_evidence"
        ]["tokens"]

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
                document["status"]
            ),
            "extraction_status": (
                extraction["status"]
            ),
            "line_item_count": (
                extraction[
                    "line_item_count"
                ]
            ),
            "line_item_confidence": (
                extraction[
                    "line_item_confidence"
                ]
            ),
            "first_description": (
                first["description"]
            ),
            "first_quantity": (
                first["quantity"]
            ),
            "first_unit_price": (
                first["unit_price"]
            ),
            "first_line_total": (
                first["line_total"]
            ),
            "raw_normalized_evidence_preserved": True,
            "elapsed_seconds": (
                elapsed_seconds
            ),
        }
    )


if __name__ == "__main__":
    main()