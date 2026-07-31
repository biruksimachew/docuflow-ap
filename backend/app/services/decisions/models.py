from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class InvoiceDecisionInput:
    """Completed control outcomes consumed by the decision policy."""

    document_id: str
    invoice_extraction_id: str

    extraction_status: str

    header_confidence: Decimal | None
    line_item_confidence: Decimal | None
    line_item_count: int

    validation_status: str
    validation_outcome: str | None
    validation_blocking_count: int

    duplicate_status: str
    duplicate_outcome: str | None
    duplicate_blocking: bool

    vendor_match_status: str
    vendor_outcome: str | None
    vendor_blocking: bool

    po_match_status: str
    po_outcome: str | None
    po_blocking: bool


@dataclass(frozen=True)
class InvoiceDecisionResult:
    """Authoritative invoice decision and evidence."""

    outcome: str
    blocking: bool

    reason_codes: tuple[str, ...]
    explanation: str

    input_snapshot: dict[str, Any]
    threshold_snapshot: dict[str, Any]