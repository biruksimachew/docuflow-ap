from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def evaluate_effective_validation(
    *,
    header: dict[str, Any],
    lines: list[dict[str, Any]],
    tolerance: Decimal,
) -> dict[str, Any]:
    blockers: list[str] = []
    checks: dict[str, Any] = {}

    required_header_fields = (
        "vendor_name",
        "invoice_number",
        "invoice_date",
        "currency",
        "subtotal",
        "total_amount",
    )

    missing_header_fields = [
        field_name
        for field_name in required_header_fields
        if header.get(field_name) in {
            None,
            "",
        }
    ]

    checks[
        "required_header_fields"
    ] = {
        "passed": (
            len(missing_header_fields)
            == 0
        ),
        "missing_fields": (
            missing_header_fields
        ),
    }

    if missing_header_fields:
        blockers.append(
            "REQUIRED_HEADER_FIELDS_MISSING"
        )

    subtotal = _decimal(
        header.get(
            "subtotal"
        )
    )

    discount = (
        _decimal(
            header.get(
                "discount_amount"
            )
        )
        or Decimal("0")
    )

    shipping = (
        _decimal(
            header.get(
                "shipping_amount"
            )
        )
        or Decimal("0")
    )

    tax = (
        _decimal(
            header.get(
                "tax_amount"
            )
        )
        or Decimal("0")
    )

    total = _decimal(
        header.get(
            "total_amount"
        )
    )

    if (
        subtotal is None
        or total is None
    ):
        header_arithmetic_passed = False
        header_difference = None
        expected_total = None
    else:
        expected_total = (
            subtotal
            - discount
            + shipping
            + tax
        )

        header_difference = abs(
            expected_total - total
        )

        header_arithmetic_passed = (
            header_difference
            <= tolerance
        )

    checks[
        "header_arithmetic"
    ] = {
        "passed": (
            header_arithmetic_passed
        ),
        "subtotal": _decimal_text(
            subtotal
        ),
        "discount_amount": (
            _decimal_text(
                discount
            )
        ),
        "shipping_amount": (
            _decimal_text(
                shipping
            )
        ),
        "tax_amount": _decimal_text(
            tax
        ),
        "expected_total": (
            _decimal_text(
                expected_total
            )
        ),
        "actual_total": (
            _decimal_text(
                total
            )
        ),
        "difference": (
            _decimal_text(
                header_difference
            )
        ),
    }

    if not header_arithmetic_passed:
        blockers.append(
            "HEADER_ARITHMETIC_FAILED"
        )

    amount_fields = {
        "subtotal": subtotal,
        "discount_amount": discount,
        "shipping_amount": shipping,
        "tax_amount": tax,
        "total_amount": total,
    }

    negative_header_amounts = [
        field_name
        for field_name, value
        in amount_fields.items()
        if (
            value is not None
            and value < Decimal("0")
        )
    ]

    checks[
        "amount_sanity"
    ] = {
        "passed": (
            not negative_header_amounts
        ),
        "negative_fields": (
            negative_header_amounts
        ),
    }

    if negative_header_amounts:
        blockers.append(
            "NEGATIVE_HEADER_AMOUNT"
        )

    if not lines:
        blockers.append(
            "NO_LINE_ITEMS"
        )

    line_results: list[
        dict[str, Any]
    ] = []

    line_sum = Decimal("0")
    all_line_arithmetic_passed = (
        len(lines) > 0
    )

    header_currency = (
        str(
            header.get(
                "currency"
            )
        ).upper()
        if header.get(
            "currency"
        )
        else None
    )

    currency_consistency_passed = (
        header_currency is not None
    )

    for line in lines:
        quantity = _decimal(
            line.get(
                "quantity"
            )
        )

        unit_price = _decimal(
            line.get(
                "unit_price"
            )
        )

        line_total = _decimal(
            line.get(
                "line_total"
            )
        )

        if (
            quantity is None
            or unit_price is None
            or line_total is None
        ):
            arithmetic_passed = False
            expected_line_total = None
            line_difference = None
        else:
            expected_line_total = (
                quantity
                * unit_price
            )

            line_difference = abs(
                expected_line_total
                - line_total
            )

            arithmetic_passed = (
                line_difference
                <= tolerance
            )

            line_sum += line_total

        line_currency = (
            str(
                line.get(
                    "currency"
                )
            ).upper()
            if line.get(
                "currency"
            )
            else header_currency
        )

        line_currency_matches = (
            header_currency is not None
            and line_currency
            == header_currency
        )

        currency_consistency_passed = (
            currency_consistency_passed
            and line_currency_matches
        )

        positive_values = (
            quantity is not None
            and quantity > Decimal("0")
            and unit_price is not None
            and unit_price >= Decimal("0")
            and line_total is not None
            and line_total >= Decimal("0")
        )

        line_passed = (
            arithmetic_passed
            and positive_values
            and bool(
                str(
                    line.get(
                        "description"
                    )
                    or ""
                ).strip()
            )
            and line_currency_matches
        )

        all_line_arithmetic_passed = (
            all_line_arithmetic_passed
            and line_passed
        )

        line_results.append(
            {
                "line_item_id": (
                    line.get(
                        "id"
                    )
                ),
                "line_number": (
                    line.get(
                        "line_number"
                    )
                ),
                "passed": line_passed,
                "description_present": bool(
                    str(
                        line.get(
                            "description"
                        )
                        or ""
                    ).strip()
                ),
                "quantity": _decimal_text(
                    quantity
                ),
                "unit_price": (
                    _decimal_text(
                        unit_price
                    )
                ),
                "expected_line_total": (
                    _decimal_text(
                        expected_line_total
                    )
                ),
                "actual_line_total": (
                    _decimal_text(
                        line_total
                    )
                ),
                "difference": (
                    _decimal_text(
                        line_difference
                    )
                ),
                "currency_matches": (
                    line_currency_matches
                ),
            }
        )

    checks[
        "line_arithmetic"
    ] = {
        "passed": (
            all_line_arithmetic_passed
        ),
        "lines": line_results,
    }

    if not all_line_arithmetic_passed:
        blockers.append(
            "LINE_ITEM_VALIDATION_FAILED"
        )

    if subtotal is None:
        line_sum_matches = False
        line_sum_difference = None
    else:
        line_sum_difference = abs(
            line_sum - subtotal
        )

        line_sum_matches = (
            len(lines) > 0
            and line_sum_difference
            <= tolerance
        )

    checks[
        "line_sum_to_subtotal"
    ] = {
        "passed": line_sum_matches,
        "line_sum": _decimal_text(
            line_sum
        ),
        "subtotal": _decimal_text(
            subtotal
        ),
        "difference": _decimal_text(
            line_sum_difference
        ),
    }

    if not line_sum_matches:
        blockers.append(
            "LINE_SUM_MISMATCH"
        )

    checks[
        "currency_consistency"
    ] = {
        "passed": (
            currency_consistency_passed
        ),
        "header_currency": (
            header_currency
        ),
    }

    if not currency_consistency_passed:
        blockers.append(
            "CURRENCY_INCONSISTENT"
        )

    blockers = list(
        dict.fromkeys(
            blockers
        )
    )

    return {
        "passed": not blockers,
        "blocking_reasons": blockers,
        "checks": checks,
    }


def _decimal(
    value: Any,
) -> Decimal | None:
    if value is None:
        return None

    try:
        result = Decimal(
            str(value)
        )
    except InvalidOperation:
        return None

    if not result.is_finite():
        return None

    return result


def _decimal_text(
    value: Decimal | None,
) -> str | None:
    if value is None:
        return None

    return format(
        value,
        "f",
    )