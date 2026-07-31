from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class InvoiceLineValidationItem:
    """Typed line-item values consumed by deterministic rules."""

    line_number: int
    description: str

    quantity: Decimal | None
    unit_price: Decimal | None
    line_total: Decimal | None

    currency: str | None


@dataclass(frozen=True)
class InvoiceValidationContext:
    """Typed invoice values consumed by deterministic rules."""

    document_id: str
    invoice_extraction_id: str

    vendor_name: str | None
    invoice_number: str | None
    raw_invoice_number: str | None

    invoice_date: date | None
    due_date: date | None

    purchase_order_number: str | None
    currency: str | None

    subtotal: Decimal | None
    discount_amount: Decimal | None
    shipping_amount: Decimal | None
    tax_amount: Decimal | None
    total_amount: Decimal | None

    line_items: tuple[
        InvoiceLineValidationItem,
        ...,
    ]


@dataclass(frozen=True)
class ValidationRuleResult:
    """One deterministic validation rule result."""

    rule_id: str
    rule_name: str

    result: str
    blocking: bool

    expected_value: Any
    actual_value: Any
    tolerance: Any

    message: str
    details: dict[str, Any]


@dataclass(frozen=True)
class ValidationSummary:
    """Aggregated deterministic validation outcome."""

    results: tuple[ValidationRuleResult, ...]

    overall_outcome: str

    passed_count: int
    warning_count: int
    failed_count: int

    blocking_rule_ids: tuple[str, ...]

    @property
    def blocking_count(self) -> int:
        return len(
            self.blocking_rule_ids
        )