import io
from uuid import uuid4

import httpx
from pypdf import PdfWriter


def create_unique_pdf() -> bytes:
    writer = PdfWriter()

    writer.add_blank_page(
        width=612,
        height=792,
    )

    writer.add_metadata(
        {
            "/Title": f"DocuFlow Smoke Test {uuid4()}",
            "/Author": "DocuFlow AP",
        }
    )

    buffer = io.BytesIO()
    writer.write(buffer)

    return buffer.getvalue()


def main() -> None:
    pdf_content = create_unique_pdf()

    files = {
        "file": (
            "Meridian Smoke Invoice.pdf",
            pdf_content,
            "application/pdf",
        )
    }

    data = {
        "source_channel": "WEB_UPLOAD",
    }

    first_response = httpx.post(
        "http://127.0.0.1:8000/api/v1/documents/upload",
        files=files,
        data=data,
        timeout=30,
    )

    first_response.raise_for_status()
    first_payload = first_response.json()

    assert first_response.status_code == 201
    assert first_payload["status"] == "RECEIVED"
    assert first_payload["is_duplicate"] is False
    assert first_payload["page_count"] == 1
    assert len(first_payload["sha256"]) == 64

    second_response = httpx.post(
        "http://127.0.0.1:8000/api/v1/documents/upload",
        files={
            "file": (
                "Same Invoice Uploaded Again.pdf",
                pdf_content,
                "application/pdf",
            )
        },
        data=data,
        timeout=30,
    )

    second_response.raise_for_status()
    second_payload = second_response.json()

    assert second_response.status_code == 200
    assert second_payload["is_duplicate"] is True
    assert (
        second_payload["document_id"]
        == first_payload["document_id"]
    )

    print(
        {
            "status": "passed",
            "document_id": first_payload["document_id"],
            "sha256": first_payload["sha256"],
            "duplicate_returned_existing_id": True,
        }
    )


if __name__ == "__main__":
    main()