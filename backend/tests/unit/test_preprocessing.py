import io

from app.services.processing.preprocessing import (
    image_to_png_bytes,
    preprocess_page,
    render_document_pages,
)
from tests.ocr_test_image import (
    create_test_invoice_image,
)


def test_png_rendering_returns_one_page() -> None:
    image = create_test_invoice_image()

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    pages = render_document_pages(
        content=buffer.getvalue(),
        media_type="image/png",
        pdf_render_dpi=200,
    )

    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert pages[0].image.width == 1600
    assert pages[0].image.height == 1000


def test_preprocessing_records_operations() -> None:
    image = create_test_invoice_image().rotate(
        2,
        expand=True,
        fillcolor="white",
    )

    result = preprocess_page(image)

    operation_names = {
        operation["operation"]
        for operation in result.operations
    }

    assert result.image.width > 0
    assert result.image.height > 0

    assert "orientation_correction" in operation_names
    assert "grayscale" in operation_names
    assert "contrast_normalization" in operation_names
    assert "median_denoise" in operation_names
    assert "deskew" in operation_names

    png_bytes = image_to_png_bytes(
        result.image
    )

    assert png_bytes.startswith(
        b"\x89PNG\r\n\x1a\n"
    )