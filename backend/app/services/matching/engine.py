from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from app.services.matching.models import (
    InvoiceMatchInput,
    PurchaseOrderMatchResult,
    PurchaseOrderRecord,
    VendorCandidate,
    VendorMatchResult,
)


def normalize_name(
    value: str,
) -> str:
    normalized = re.sub(
        r"[\W_]+",
        " ",
        value.upper(),
        flags=re.UNICODE,
    )

    return re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()


def normalize_identifier(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        value.strip(),
    ).upper()


def resolve_vendor_identity(
    *,
    input_vendor_name: str | None,
    candidates: tuple[
        VendorCandidate,
        ...,
    ],
) -> VendorMatchResult:
    """Resolve an extracted supplier name against the vendor master."""

    normalized_input = (
        normalize_name(
            input_vendor_name
        )
        if input_vendor_name
        else None
    )

    if not normalized_input:
        return VendorMatchResult(
            input_vendor_name=input_vendor_name,
            normalized_input_name=None,
            outcome="UNMATCHED",
            blocking=True,
            candidates=(),
            matched_vendor_id=None,
            evidence={
                "reason": (
                    "The canonical vendor name is missing."
                ),
            },
        )

    if len(candidates) == 1:
        candidate = candidates[0]

        return VendorMatchResult(
            input_vendor_name=input_vendor_name,
            normalized_input_name=(
                normalized_input
            ),
            outcome="MATCHED",
            blocking=False,
            candidates=candidates,
            matched_vendor_id=(
                candidate.vendor_id
            ),
            evidence={
                "matching_method": (
                    "exact_normalized_vendor_or_alias"
                ),
                "matched_on": (
                    candidate.matched_on
                ),
                "vendor_code": (
                    candidate.vendor_code
                ),
                "canonical_name": (
                    candidate.canonical_name
                ),
            },
        )

    if len(candidates) > 1:
        return VendorMatchResult(
            input_vendor_name=input_vendor_name,
            normalized_input_name=(
                normalized_input
            ),
            outcome="AMBIGUOUS",
            blocking=True,
            candidates=candidates,
            matched_vendor_id=None,
            evidence={
                "reason": (
                    "Multiple active vendor-master records "
                    "match the normalized supplier identity."
                ),
                "candidate_vendor_ids": [
                    candidate.vendor_id
                    for candidate in candidates
                ],
            },
        )

    return VendorMatchResult(
        input_vendor_name=input_vendor_name,
        normalized_input_name=(
            normalized_input
        ),
        outcome="UNMATCHED",
        blocking=True,
        candidates=(),
        matched_vendor_id=None,
        evidence={
            "reason": (
                "No active vendor-master name or alias "
                "matches the canonical supplier name."
            ),
        },
    )


def evaluate_purchase_order_match(
    *,
    invoice: InvoiceMatchInput,
    resolved_vendor_id: str | None,
    purchase_order: PurchaseOrderRecord | None,
    tolerance: Decimal,
) -> PurchaseOrderMatchResult:
    """Compare canonical invoice values with a purchase order."""

    normalized_tolerance = abs(
        tolerance
    )

    if not invoice.purchase_order_number:
        return PurchaseOrderMatchResult(
            input_po_number=None,
            outcome="NOT_PROVIDED",
            blocking=True,
            matched_purchase_order_id=None,
            matched_line_count=0,
            mismatched_line_count=0,
            check_results={
                "purchase_order_number_present": False,
                "message": (
                    "No purchase-order number was "
                    "extracted from the invoice."
                ),
            },
        )

    normalized_po_number = normalize_identifier(
        invoice.purchase_order_number
    )

    if resolved_vendor_id is None:
        return PurchaseOrderMatchResult(
            input_po_number=(
                normalized_po_number
            ),
            outcome="VENDOR_UNRESOLVED",
            blocking=True,
            matched_purchase_order_id=(
                purchase_order.purchase_order_id
                if purchase_order
                else None
            ),
            matched_line_count=0,
            mismatched_line_count=0,
            check_results={
                "purchase_order_number_present": True,
                "vendor_resolved": False,
                "message": (
                    "Purchase-order matching cannot be "
                    "completed until vendor identity is "
                    "resolved."
                ),
            },
        )

    if purchase_order is None:
        return PurchaseOrderMatchResult(
            input_po_number=(
                normalized_po_number
            ),
            outcome="NOT_FOUND",
            blocking=True,
            matched_purchase_order_id=None,
            matched_line_count=0,
            mismatched_line_count=0,
            check_results={
                "purchase_order_number_present": True,
                "purchase_order_found": False,
                "message": (
                    "No purchase order exists for the "
                    "extracted PO number."
                ),
            },
        )

    status_matches = (
        purchase_order.status == "OPEN"
    )

    vendor_matches = (
        purchase_order.vendor_id
        == resolved_vendor_id
    )

    currency_matches = _same_present_text(
        invoice.currency,
        purchase_order.currency,
    )

    subtotal_check = _amount_check(
        actual=invoice.subtotal,
        expected=purchase_order.subtotal,
        tolerance=normalized_tolerance,
    )

    tax_check = _amount_check(
        actual=invoice.tax_amount,
        expected=purchase_order.tax_amount,
        tolerance=normalized_tolerance,
    )

    total_check = _amount_check(
        actual=invoice.total_amount,
        expected=purchase_order.total_amount,
        tolerance=normalized_tolerance,
    )

    po_lines_by_description = {
        line.normalized_description: line
        for line in purchase_order.lines
    }

    line_results: list[dict[str, Any]] = []
    matched_line_count = 0
    mismatched_line_count = 0

    for invoice_line in invoice.lines:
        po_line = po_lines_by_description.get(
            invoice_line.normalized_description
        )

        if po_line is None:
            mismatched_line_count += 1

            line_results.append(
                {
                    "invoice_line_number": (
                        invoice_line.line_number
                    ),
                    "description": (
                        invoice_line.description
                    ),
                    "result": "NOT_FOUND",
                    "quantity_matches": False,
                    "unit_price_matches": False,
                    "line_total_matches": False,
                }
            )

            continue

        quantity_check = _amount_check(
            actual=invoice_line.quantity,
            expected=po_line.quantity,
            tolerance=normalized_tolerance,
        )

        unit_price_check = _amount_check(
            actual=invoice_line.unit_price,
            expected=po_line.unit_price,
            tolerance=normalized_tolerance,
        )

        line_total_check = _amount_check(
            actual=invoice_line.line_total,
            expected=po_line.line_total,
            tolerance=normalized_tolerance,
        )

        line_matches = (
            quantity_check["matches"]
            and unit_price_check["matches"]
            and line_total_check["matches"]
        )

        if line_matches:
            matched_line_count += 1
        else:
            mismatched_line_count += 1

        line_results.append(
            {
                "invoice_line_number": (
                    invoice_line.line_number
                ),
                "purchase_order_line_number": (
                    po_line.line_number
                ),
                "description": (
                    invoice_line.description
                ),
                "result": (
                    "MATCHED"
                    if line_matches
                    else "MISMATCHED"
                ),
                "quantity": quantity_check,
                "unit_price": unit_price_check,
                "line_total": line_total_check,
            }
        )

    line_count_matches = (
        len(invoice.lines)
        == len(purchase_order.lines)
        and len(invoice.lines) > 0
    )

    line_items_match = (
        line_count_matches
        and mismatched_line_count == 0
        and matched_line_count
        == len(invoice.lines)
    )

    checks = {
        "purchase_order_number_present": True,
        "purchase_order_found": True,
        "purchase_order_status_open": (
            status_matches
        ),
        "vendor_matches": (
            vendor_matches
        ),
        "currency_matches": (
            currency_matches
        ),
        "subtotal": subtotal_check,
        "tax_amount": tax_check,
        "total_amount": total_check,
        "line_count_matches": (
            line_count_matches
        ),
        "line_items_match": (
            line_items_match
        ),
        "line_results": line_results,
        "invoice_line_count": len(
            invoice.lines
        ),
        "purchase_order_line_count": len(
            purchase_order.lines
        ),
        "tolerance": _decimal_text(
            normalized_tolerance
        ),
    }

    matched = (
        status_matches
        and vendor_matches
        and currency_matches
        and subtotal_check["matches"]
        and tax_check["matches"]
        and total_check["matches"]
        and line_items_match
    )

    return PurchaseOrderMatchResult(
        input_po_number=normalized_po_number,
        outcome=(
            "MATCHED"
            if matched
            else "MISMATCHED"
        ),
        blocking=not matched,
        matched_purchase_order_id=(
            purchase_order.purchase_order_id
        ),
        matched_line_count=(
            matched_line_count
        ),
        mismatched_line_count=(
            mismatched_line_count
        ),
        check_results=checks,
    )


def _amount_check(
    *,
    actual: Decimal | None,
    expected: Decimal | None,
    tolerance: Decimal,
) -> dict[str, Any]:
    if (
        actual is None
        or expected is None
    ):
        return {
            "matches": False,
            "expected": _decimal_text(
                expected
            ),
            "actual": _decimal_text(
                actual
            ),
            "difference": None,
        }

    difference = abs(
        actual - expected
    )

    return {
        "matches": (
            difference <= tolerance
        ),
        "expected": _decimal_text(
            expected
        ),
        "actual": _decimal_text(
            actual
        ),
        "difference": _decimal_text(
            difference
        ),
    }


def _same_present_text(
    left: str | None,
    right: str | None,
) -> bool:
    return (
        left is not None
        and right is not None
        and left.strip().upper()
        == right.strip().upper()
    )


def _decimal_text(
    value: Decimal | None,
) -> str | None:
    if value is None:
        return None

    fixed_value = format(
        value,
        "f",
    )

    if "." not in fixed_value:
        return f"{fixed_value}.00"

    whole, fraction = fixed_value.split(
        ".",
        1,
    )

    fraction = fraction.rstrip("0")

    if len(fraction) < 2:
        fraction = fraction.ljust(
            2,
            "0",
        )

    return f"{whole}.{fraction}"