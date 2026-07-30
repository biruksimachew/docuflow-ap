from app.services.ocr.factory import (
    get_ocr_provider,
)
from tests.ocr_test_image import (
    create_test_invoice_image,
)


def main() -> None:
    provider = get_ocr_provider()

    result = provider.extract_page(
        create_test_invoice_image()
    )

    normalized_text = result.text.upper()

    required_values = (
        "INVOICE",
        "INV-1001",
        "138.00",
    )

    for required_value in required_values:
        if required_value not in normalized_text:
            raise RuntimeError(
                f"OCR did not find: {required_value}"
            )

    print(
        {
            "status": "passed",
            "provider": result.provider,
            "provider_version": result.provider_version,
            "language": result.language,
            "average_confidence": result.average_confidence,
            "token_count": len(result.tokens),
            "detected_invoice_number": "INV-1001",
            "detected_total": "138.00",
        }
    )


if __name__ == "__main__":
    main()