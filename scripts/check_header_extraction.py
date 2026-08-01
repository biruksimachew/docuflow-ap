import io
import time
from uuid import uuid4

import httpx

from scripts.auth_test_tokens import (
    authenticated_get,
)
from PIL import ImageDraw

from tests.ocr_test_image import (
    create_test_invoice_image,
)


def create_unique_invoice_png() -> bytes:
    image = create_test_invoice_image()

    draw = ImageDraw.Draw(image)

    draw.text(
        (1030, 950),
        f"Header extraction {uuid4()}",
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
                "Meridian Header Extraction Invoice.png",
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
    assert upload_payload["processing_enqueued"] is True

    document_id = upload_payload[
        "document_id"
    ]

    processing_snapshot = None

    for _ in range(60):
        processing_response = authenticated_get(
            (
                "http://127.0.0.1:8000"
                f"/api/v1/documents/{document_id}"
                "/processing"
            ),
            timeout=20,
        )

        processing_response.raise_for_status()

        processing_snapshot = (
            processing_response.json()
        )

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

    extraction_response = authenticated_get(
        (
            "http://127.0.0.1:8000"
            f"/api/v1/documents/{document_id}"
            "/extraction"
        ),
        timeout=20,
    )

    extraction_response.raise_for_status()

    snapshot = extraction_response.json()

    extraction = snapshot[
        "invoice_extraction"
    ]

    assert extraction is not None
    assert extraction["status"] == "SUCCEEDED"
    assert extraction["schema_version"] == "header-v1"
    assert extraction["header_confidence"] > 0.80
    assert extraction["missing_required_fields"] == []

    header = snapshot[
        "canonical_header"
    ]

    assert header is not None

    assert (
        header["vendor_name"]
        == "Meridian Office Supplies"
    )

    assert (
        header["invoice_number"]
        == "INV-1001"
    )

    assert (
        header["invoice_date"]
        == "2026-07-30"
    )

    assert header["currency"] == "USD"

    fields = {
        field["field_name"]: field
        for field in snapshot[
            "extracted_fields"
        ]
    }

    assert (
        fields["invoice_number"][
            "normalized_text"
        ]
        == "INV-1001"
    )

    assert (
        fields["total_amount"][
            "normalized_text"
        ]
        == "138.00"
    )

    for required_field in (
        "vendor_name",
        "invoice_number",
        "invoice_date",
        "currency",
        "total_amount",
    ):
        field = fields[required_field]

        assert field["raw_value"]
        assert field["normalized_text"]
        assert field["confidence"] > 0
        assert field["page_number"] == 1
        assert field["extraction_method"]

        evidence = field["evidence"]

        assert evidence["page_number"] == 1
        assert evidence["line_text"]
        assert evidence["bounding_box"]
        assert evidence["tokens"]

    elapsed_seconds = round(
        time.monotonic() - started_at,
        2,
    )

    print(
        {
            "status": "passed",
            "document_id": document_id,
            "document_status": document["status"],
            "extraction_status": extraction["status"],
            "schema_version": extraction["schema_version"],
            "header_confidence": extraction[
                "header_confidence"
            ],
            "field_count": extraction[
                "extracted_field_count"
            ],
            "vendor_name": header["vendor_name"],
            "invoice_number": header["invoice_number"],
            "invoice_date": header["invoice_date"],
            "currency": header["currency"],
            "subtotal": fields["subtotal"][
                "normalized_text"
            ],
            "tax_amount": fields["tax_amount"][
                "normalized_text"
            ],
            "total_amount": fields["total_amount"][
                "normalized_text"
            ],
            "raw_normalized_evidence_preserved": True,
            "elapsed_seconds": elapsed_seconds,
        }
    )


if __name__ == "__main__":
    main()