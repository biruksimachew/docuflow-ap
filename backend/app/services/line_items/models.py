from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class LineItemCandidate:
    """One canonical invoice line extracted from OCR evidence."""

    line_number: int

    description: str
    supplier_sku: str | None

    quantity: Decimal | None
    unit_of_measure: str | None

    unit_price: Decimal | None
    tax_rate: Decimal | None
    line_total: Decimal | None

    currency: str | None

    confidence: float
    confidence_source: str
    extraction_method: str

    page_number: int
    raw_row_text: str

    normalized_values: dict[str, Any]
    field_evidence: dict[str, Any]
    row_evidence: dict[str, Any]


@dataclass(frozen=True)
class LineItemExtractionResult:
    """Aggregated canonical line-item extraction output."""

    items: tuple[LineItemCandidate, ...]

    average_confidence: float | None

    @property
    def item_count(self) -> int:
        return len(self.items)