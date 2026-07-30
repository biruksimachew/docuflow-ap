from app.services.ocr.tesseract import (
    TesseractOCRProvider,
)
from tests.ocr_test_image import (
    create_test_invoice_image,
)


def test_tesseract_extracts_invoice_text() -> None:
    provider = TesseractOCRProvider(
        language="eng"
    )

    result = provider.extract_page(
        create_test_invoice_image()
    )

    normalized_text = result.text.upper()

    assert result.provider == "tesseract"
    assert result.provider_version
    assert result.width_px == 1600
    assert result.height_px == 1000

    assert "INVOICE" in normalized_text
    assert "INV-1001" in normalized_text
    assert "138.00" in normalized_text

    assert result.tokens
    assert result.average_confidence is not None

    for token in result.tokens:
        assert 0 <= token.confidence <= 1
        assert token.width > 0
        assert token.height > 0