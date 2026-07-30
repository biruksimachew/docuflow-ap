from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PIL import Image


@dataclass(frozen=True)
class OCRToken:
    """One OCR token and its page-region evidence."""

    text: str
    confidence: float

    left: int
    top: int
    width: int
    height: int

    block_number: int
    paragraph_number: int
    line_number: int
    word_number: int


@dataclass(frozen=True)
class OCRPageResult:
    """Normalized OCR output for one document page."""

    provider: str
    provider_version: str
    language: str

    width_px: int
    height_px: int

    text: str
    average_confidence: float | None

    tokens: tuple[OCRToken, ...]


class OCRProvider(Protocol):
    """Provider interface implemented by every OCR engine."""

    @property
    def name(self) -> str:
        ...

    @property
    def version(self) -> str:
        ...

    def extract_page(
        self,
        image: Image.Image,
    ) -> OCRPageResult:
        ...