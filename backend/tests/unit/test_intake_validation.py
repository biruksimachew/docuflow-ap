import io

from pypdf import PdfWriter

from app.services.intake.validation import (
    sanitize_filename,
    validate_upload,
)


def create_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(
        width=612,
        height=792,
    )

    buffer = io.BytesIO()
    writer.write(buffer)

    return buffer.getvalue()


def test_sanitize_filename_removes_unsafe_characters() -> None:
    result = sanitize_filename(
        "../../Supplier Invoice #1001!!.pdf",
        "application/pdf",
    )

    assert result == "Supplier-Invoice-1001.pdf"
    assert ".." not in result
    assert "/" not in result
    assert "\\" not in result


def test_validate_pdf_generates_checksum_and_page_count() -> None:
    content = create_pdf()

    result = validate_upload(
        content=content,
        original_filename="invoice.pdf",
        declared_media_type="application/pdf",
        maximum_size_bytes=20 * 1024 * 1024,
        maximum_pages=30,
        allowed_media_types={
            "application/pdf",
            "image/jpeg",
            "image/png",
        },
    )

    assert result.detected_media_type == "application/pdf"
    assert result.page_count == 1
    assert len(result.sha256) == 64
    assert result.quarantine_reason is None