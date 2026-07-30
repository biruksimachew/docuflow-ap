from __future__ import annotations

from statistics import mean

import pytesseract
from PIL import Image
from pytesseract import Output

from app.services.ocr.base import (
    OCRPageResult,
    OCRToken,
)


class TesseractOCRProvider:
    """Local Tesseract OCR implementation."""

    def __init__(
        self,
        language: str = "eng",
    ) -> None:
        self.language = language

    @property
    def name(self) -> str:
        return "tesseract"

    @property
    def version(self) -> str:
        return str(
            pytesseract.get_tesseract_version()
        ).splitlines()[0]

    def extract_page(
        self,
        image: Image.Image,
    ) -> OCRPageResult:
        prepared_image = image.convert("RGB")

        data = pytesseract.image_to_data(
            prepared_image,
            lang=self.language,
            config="--oem 3 --psm 6",
            output_type=Output.DICT,
        )

        tokens: list[OCRToken] = []
        accepted_confidences: list[float] = []

        text_values = data.get("text", [])

        for index, raw_text in enumerate(text_values):
            token_text = str(raw_text).strip()

            if not token_text:
                continue

            try:
                confidence = float(
                    data["conf"][index]
                )
            except (KeyError, TypeError, ValueError):
                confidence = -1.0

            if confidence < 0:
                continue

            accepted_confidences.append(confidence)

            tokens.append(
                OCRToken(
                    text=token_text,
                    confidence=round(confidence / 100, 4),
                    left=int(data["left"][index]),
                    top=int(data["top"][index]),
                    width=int(data["width"][index]),
                    height=int(data["height"][index]),
                    block_number=int(
                        data["block_num"][index]
                    ),
                    paragraph_number=int(
                        data["par_num"][index]
                    ),
                    line_number=int(
                        data["line_num"][index]
                    ),
                    word_number=int(
                        data["word_num"][index]
                    ),
                )
            )

        extracted_text = pytesseract.image_to_string(
            prepared_image,
            lang=self.language,
            config="--oem 3 --psm 6",
        ).strip()

        average_confidence = None

        if accepted_confidences:
            average_confidence = round(
                mean(accepted_confidences) / 100,
                4,
            )

        return OCRPageResult(
            provider=self.name,
            provider_version=self.version,
            language=self.language,
            width_px=prepared_image.width,
            height_px=prepared_image.height,
            text=extracted_text,
            average_confidence=average_confidence,
            tokens=tuple(tokens),
        )