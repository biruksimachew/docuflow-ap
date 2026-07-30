from functools import lru_cache

from app.core.config import settings
from app.services.ocr.base import OCRProvider
from app.services.ocr.tesseract import (
    TesseractOCRProvider,
)


@lru_cache
def get_ocr_provider() -> OCRProvider:
    """Return the OCR provider selected by configuration."""

    provider_name = settings.ocr_provider.strip().lower()

    if provider_name == "tesseract":
        return TesseractOCRProvider(
            language=settings.ocr_language,
        )

    raise RuntimeError(
        f"Unsupported OCR provider: {provider_name}"
    )