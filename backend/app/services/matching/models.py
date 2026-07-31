from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class VendorCandidate:
    """One vendor-master candidate."""

    vendor_id: str
    vendor_code: str
    canonical_name: str
    normalized_name: str
    matched_on: str


@dataclass(frozen=True)
class VendorMatchResult:
    """Deterministic vendor-resolution result."""

    input_vendor_name: str | None
    normalized_input_name: str | None

    outcome: str
    blocking: bool

    candidates: tuple[
        VendorCandidate,
        ...,
    ]

    matched_vendor_id: str | None

    evidence: dict[str, Any]


@dataclass(frozen=True)
class InvoiceMatchLine:
    """Canonical invoice line used for PO matching."""

    line_number: int
    description: str
    normalized_description: str

    quantity: Decimal | None
    unit_price: Decimal | None
    line_total: Decimal | None


@dataclass(frozen=True)
class InvoiceMatchInput:
    """Canonical invoice values used for matching."""

    document_id: str
    invoice_extraction_id: str

    vendor_name: str | None
    purchase_order_number: str | None
    currency: str | None

    subtotal: Decimal | None
    tax_amount: Decimal | None
    total_amount: Decimal | None

    lines: tuple[
        InvoiceMatchLine,
        ...,
    ]


@dataclass(frozen=True)
class PurchaseOrderLine:
    """Purchase-order line used for deterministic comparison."""

    line_number: int
    description: str
    normalized_description: str

    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class PurchaseOrderRecord:
    """Purchase-order header and lines."""

    purchase_order_id: str
    po_number: str

    vendor_id: str
    currency: str
    status: str

    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal

    lines: tuple[
        PurchaseOrderLine,
        ...,
    ]


@dataclass(frozen=True)
class PurchaseOrderMatchResult:
    """Deterministic invoice-to-PO result."""

    input_po_number: str | None

    outcome: str
    blocking: bool

    matched_purchase_order_id: str | None

    matched_line_count: int
    mismatched_line_count: int

    check_results: dict[str, Any]