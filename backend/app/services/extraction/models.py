from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OCRPageInput:
    """OCR page information consumed by the extraction engine."""

    page_number: int
    raw_text: str
    average_confidence: float | None
    tokens: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class OCRLine:
    """One reconstructed OCR line with page evidence."""

    page_number: int
    text: str
    confidence: float

    tokens: tuple[dict[str, Any], ...]
    bounding_box: dict[str, int] | None


@dataclass(frozen=True)
class ExtractedFieldCandidate:
    """One normalized field candidate and its evidence."""

    field_name: str

    raw_value: str
    normalized_value: str

    confidence: float
    confidence_source: str

    extraction_method: str
    page_number: int

    evidence: dict[str, Any]


@dataclass(frozen=True)
class HeaderExtractionResult:
    """Canonical header extraction result."""

    fields: tuple[ExtractedFieldCandidate, ...]

    canonical_header: dict[str, str | None]

    header_confidence: float
    missing_required_fields: tuple[str, ...]