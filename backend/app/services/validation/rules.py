from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal

from app.services.validation.models import (
    InvoiceValidationContext,
    ValidationRuleResult,
    ValidationSummary,
)


REQUIRED_FIELDS = (
    "vendor_name",
    "invoice_number",
    "invoice_date",
    "currency",
    "total_amount",
)


def validate_invoice_header(
    *,
    context: InvoiceValidationContext,
    allowed_currencies: set[str],
    currency_tolerance: Decimal,
    future_tolerance_days: int,
    today: date | None = None,
) -> ValidationSummary:
    """
    Run the approved header and line-level deterministic controls.
    """

    evaluation_date = today or date.today()

    results = (
        _validate_required_fields(
            context
        ),
        _validate_header_arithmetic(
            context,
            currency_tolerance,
        ),
        _validate_line_sum(
            context,
            currency_tolerance,
        ),
        _validate_line_arithmetic(
            context,
            currency_tolerance,
        ),
        _validate_date_sanity(
            context,
            evaluation_date,
            future_tolerance_days,
        ),
        _validate_currency_consistency(
            context,
            allowed_currencies,
        ),
        _validate_amount_sanity(
            context
        ),
        _validate_invoice_number_normalization(
            context
        ),
    )

    passed_count = sum(
        result.result == "PASS"
        for result in results
    )

    warning_count = sum(
        result.result == "WARNING"
        for result in results
    )

    failed_count = sum(
        result.result == "FAIL"
        for result in results
    )

    blocking_rule_ids = tuple(
        result.rule_id
        for result in results
        if (
            result.blocking
            and result.result != "PASS"
        )
    )

    overall_outcome = (
        "REVIEW_REQUIRED"
        if blocking_rule_ids
        else "PASSED_CONTROLS"
    )

    return ValidationSummary(
        results=results,
        overall_outcome=overall_outcome,
        passed_count=passed_count,
        warning_count=warning_count,
        failed_count=failed_count,
        blocking_rule_ids=blocking_rule_ids,
    )


def normalize_invoice_number(
    value: str,
) -> str:
    """
    Trim and case-normalize without removing meaningful separators.
    """

    return re.sub(
        r"\s+",
        " ",
        value.strip(),
    ).upper()


def _validate_required_fields(
    context: InvoiceValidationContext,
) -> ValidationRuleResult:
    missing_fields = [
        field_name
        for field_name in REQUIRED_FIELDS
        if getattr(
            context,
            field_name,
        ) in {
            None,
            "",
        }
    ]

    if missing_fields:
        return ValidationRuleResult(
            rule_id="VAL-01",
            rule_name="Required fields",
            result="FAIL",
            blocking=True,
            expected_value={
                "required_fields": list(
                    REQUIRED_FIELDS
                ),
            },
            actual_value={
                "missing_fields": missing_fields,
            },
            tolerance=None,
            message=(
                "One or more mandatory invoice fields "
                "are missing."
            ),
            details={
                "missing_fields": missing_fields,
            },
        )

    return ValidationRuleResult(
        rule_id="VAL-01",
        rule_name="Required fields",
        result="PASS",
        blocking=False,
        expected_value={
            "required_fields": list(
                REQUIRED_FIELDS
            ),
        },
        actual_value={
            "missing_fields": [],
        },
        tolerance=None,
        message=(
            "All mandatory invoice header fields "
            "are present."
        ),
        details={},
    )


def _validate_header_arithmetic(
    context: InvoiceValidationContext,
    tolerance: Decimal,
) -> ValidationRuleResult:
    normalized_tolerance = abs(
        tolerance
    )

    if (
        context.subtotal is None
        or context.total_amount is None
    ):
        return ValidationRuleResult(
            rule_id="VAL-02",
            rule_name="Header arithmetic",
            result="WARNING",
            blocking=True,
            expected_value={
                "formula": (
                    "subtotal - discount + shipping "
                    "+ tax = total"
                ),
            },
            actual_value={
                "subtotal": _decimal_text(
                    context.subtotal
                ),
                "total_amount": _decimal_text(
                    context.total_amount
                ),
            },
            tolerance={
                "absolute_difference": _decimal_text(
                    normalized_tolerance
                ),
                "currency": context.currency,
            },
            message=(
                "Header arithmetic could not be proven "
                "because subtotal or total is missing."
            ),
            details={
                "not_evaluated": True,
            },
        )

    discount = (
        context.discount_amount
        if context.discount_amount is not None
        else Decimal("0")
    )

    shipping = (
        context.shipping_amount
        if context.shipping_amount is not None
        else Decimal("0")
    )

    tax = (
        context.tax_amount
        if context.tax_amount is not None
        else Decimal("0")
    )

    expected_total = (
        context.subtotal
        - discount
        + shipping
        + tax
    )

    difference = abs(
        expected_total
        - context.total_amount
    )

    passed = (
        difference
        <= normalized_tolerance
    )

    return ValidationRuleResult(
        rule_id="VAL-02",
        rule_name="Header arithmetic",
        result=(
            "PASS"
            if passed
            else "FAIL"
        ),
        blocking=not passed,
        expected_value={
            "calculated_total": _decimal_text(
                expected_total
            ),
            "formula": (
                "subtotal - discount + shipping "
                "+ tax"
            ),
        },
        actual_value={
            "subtotal": _decimal_text(
                context.subtotal
            ),
            "discount_amount": _decimal_text(
                discount
            ),
            "shipping_amount": _decimal_text(
                shipping
            ),
            "tax_amount": _decimal_text(
                tax
            ),
            "stated_total": _decimal_text(
                context.total_amount
            ),
            "difference": _decimal_text(
                difference
            ),
        },
        tolerance={
            "absolute_difference": _decimal_text(
                normalized_tolerance
            ),
            "currency": context.currency,
        },
        message=(
            "Header arithmetic reconciles within "
            "the configured tolerance."
            if passed
            else (
                "The stated invoice total does not "
                "reconcile with subtotal, discount, "
                "shipping and tax."
            )
        ),
        details={
            "not_evaluated": False,
        },
    )


def _validate_line_sum(
    context: InvoiceValidationContext,
    tolerance: Decimal,
) -> ValidationRuleResult:
    normalized_tolerance = abs(
        tolerance
    )

    if not context.line_items:
        return ValidationRuleResult(
            rule_id="VAL-03",
            rule_name="Line totals to subtotal",
            result="WARNING",
            blocking=True,
            expected_value={
                "formula": (
                    "sum(line_total) = subtotal"
                ),
            },
            actual_value={
                "line_item_count": 0,
                "subtotal": _decimal_text(
                    context.subtotal
                ),
            },
            tolerance={
                "absolute_difference": _decimal_text(
                    normalized_tolerance
                ),
                "currency": context.currency,
            },
            message=(
                "Line-total reconciliation could not "
                "be proven because no line items were "
                "extracted."
            ),
            details={
                "not_evaluated": True,
            },
        )

    if context.subtotal is None:
        return ValidationRuleResult(
            rule_id="VAL-03",
            rule_name="Line totals to subtotal",
            result="WARNING",
            blocking=True,
            expected_value={
                "formula": (
                    "sum(line_total) = subtotal"
                ),
            },
            actual_value={
                "line_item_count": len(
                    context.line_items
                ),
                "subtotal": None,
            },
            tolerance={
                "absolute_difference": _decimal_text(
                    normalized_tolerance
                ),
                "currency": context.currency,
            },
            message=(
                "Line-total reconciliation could not "
                "be proven because subtotal is missing."
            ),
            details={
                "not_evaluated": True,
            },
        )

    missing_line_numbers = [
        item.line_number
        for item in context.line_items
        if item.line_total is None
    ]

    if missing_line_numbers:
        return ValidationRuleResult(
            rule_id="VAL-03",
            rule_name="Line totals to subtotal",
            result="WARNING",
            blocking=True,
            expected_value={
                "formula": (
                    "sum(line_total) = subtotal"
                ),
            },
            actual_value={
                "subtotal": _decimal_text(
                    context.subtotal
                ),
                "missing_line_total_numbers": (
                    missing_line_numbers
                ),
            },
            tolerance={
                "absolute_difference": _decimal_text(
                    normalized_tolerance
                ),
                "currency": context.currency,
            },
            message=(
                "Line-total reconciliation could not "
                "be proven because one or more line "
                "totals are missing."
            ),
            details={
                "not_evaluated": True,
                "missing_line_numbers": (
                    missing_line_numbers
                ),
            },
        )

    calculated_line_sum = sum(
        (
            item.line_total
            for item in context.line_items
            if item.line_total is not None
        ),
        Decimal("0"),
    )

    difference = abs(
        calculated_line_sum
        - context.subtotal
    )

    passed = (
        difference
        <= normalized_tolerance
    )

    return ValidationRuleResult(
        rule_id="VAL-03",
        rule_name="Line totals to subtotal",
        result=(
            "PASS"
            if passed
            else "FAIL"
        ),
        blocking=not passed,
        expected_value={
            "subtotal": _decimal_text(
                context.subtotal
            ),
            "formula": (
                "sum(line_total)"
            ),
        },
        actual_value={
            "calculated_line_sum": _decimal_text(
                calculated_line_sum
            ),
            "difference": _decimal_text(
                difference
            ),
            "line_item_count": len(
                context.line_items
            ),
        },
        tolerance={
            "absolute_difference": _decimal_text(
                normalized_tolerance
            ),
            "currency": context.currency,
        },
        message=(
            "The sum of canonical line totals matches "
            "the invoice subtotal."
            if passed
            else (
                "The sum of canonical line totals does "
                "not match the invoice subtotal."
            )
        ),
        details={
            "not_evaluated": False,
            "line_totals": [
                {
                    "line_number": item.line_number,
                    "line_total": _decimal_text(
                        item.line_total
                    ),
                }
                for item in context.line_items
            ],
        },
    )


def _validate_line_arithmetic(
    context: InvoiceValidationContext,
    tolerance: Decimal,
) -> ValidationRuleResult:
    normalized_tolerance = abs(
        tolerance
    )

    if not context.line_items:
        return ValidationRuleResult(
            rule_id="VAL-04",
            rule_name="Line arithmetic",
            result="WARNING",
            blocking=True,
            expected_value={
                "formula": (
                    "quantity × unit_price = line_total"
                ),
            },
            actual_value={
                "line_item_count": 0,
            },
            tolerance={
                "absolute_difference": _decimal_text(
                    normalized_tolerance
                ),
                "currency": context.currency,
            },
            message=(
                "Line arithmetic could not be proven "
                "because no line items were extracted."
            ),
            details={
                "not_evaluated": True,
                "line_results": [],
            },
        )

    line_results: list[dict] = []
    incomplete_line_numbers: list[int] = []
    failed_line_numbers: list[int] = []

    for item in context.line_items:
        if (
            item.quantity is None
            or item.unit_price is None
            or item.line_total is None
        ):
            incomplete_line_numbers.append(
                item.line_number
            )

            line_results.append(
                {
                    "line_number": item.line_number,
                    "description": item.description,
                    "result": "NOT_EVALUATED",
                    "quantity": _decimal_text(
                        item.quantity
                    ),
                    "unit_price": _decimal_text(
                        item.unit_price
                    ),
                    "stated_line_total": _decimal_text(
                        item.line_total
                    ),
                }
            )

            continue

        calculated_total = (
            item.quantity
            * item.unit_price
        )

        difference = abs(
            calculated_total
            - item.line_total
        )

        passed = (
            difference
            <= normalized_tolerance
        )

        if not passed:
            failed_line_numbers.append(
                item.line_number
            )

        line_results.append(
            {
                "line_number": item.line_number,
                "description": item.description,
                "result": (
                    "PASS"
                    if passed
                    else "FAIL"
                ),
                "quantity": _decimal_text(
                    item.quantity
                ),
                "unit_price": _decimal_text(
                    item.unit_price
                ),
                "calculated_line_total": (
                    _decimal_text(
                        calculated_total
                    )
                ),
                "stated_line_total": (
                    _decimal_text(
                        item.line_total
                    )
                ),
                "difference": _decimal_text(
                    difference
                ),
            }
        )

    if failed_line_numbers:
        result = "FAIL"
        message = (
            "One or more invoice lines fail the "
            "quantity multiplied by unit-price check."
        )
    elif incomplete_line_numbers:
        result = "WARNING"
        message = (
            "Line arithmetic could not be proven for "
            "one or more incomplete invoice lines."
        )
    else:
        result = "PASS"
        message = (
            "Every canonical invoice line reconciles "
            "within the configured tolerance."
        )

    return ValidationRuleResult(
        rule_id="VAL-04",
        rule_name="Line arithmetic",
        result=result,
        blocking=(
            result != "PASS"
        ),
        expected_value={
            "formula": (
                "quantity × unit_price = line_total"
            ),
            "evaluated_line_count": len(
                context.line_items
            ),
        },
        actual_value={
            "failed_line_numbers": (
                failed_line_numbers
            ),
            "incomplete_line_numbers": (
                incomplete_line_numbers
            ),
        },
        tolerance={
            "absolute_difference": _decimal_text(
                normalized_tolerance
            ),
            "currency": context.currency,
        },
        message=message,
        details={
            "not_evaluated": False,
            "line_results": line_results,
        },
    )


def _validate_date_sanity(
    context: InvoiceValidationContext,
    today: date,
    future_tolerance_days: int,
) -> ValidationRuleResult:
    if context.invoice_date is None:
        return ValidationRuleResult(
            rule_id="VAL-05",
            rule_name="Date sanity",
            result="FAIL",
            blocking=True,
            expected_value={
                "invoice_date_present": True,
            },
            actual_value={
                "invoice_date": None,
                "due_date": _date_text(
                    context.due_date
                ),
            },
            tolerance={
                "future_days": (
                    future_tolerance_days
                ),
            },
            message=(
                "Date sanity cannot be validated "
                "because invoice date is missing."
            ),
            details={},
        )

    future_limit = (
        today
        + timedelta(
            days=max(
                0,
                future_tolerance_days,
            )
        )
    )

    if context.invoice_date > future_limit:
        return ValidationRuleResult(
            rule_id="VAL-05",
            rule_name="Date sanity",
            result="FAIL",
            blocking=True,
            expected_value={
                "latest_allowed_invoice_date": (
                    future_limit.isoformat()
                ),
                "due_date_not_before_invoice_date": True,
            },
            actual_value={
                "invoice_date": (
                    context.invoice_date.isoformat()
                ),
                "due_date": _date_text(
                    context.due_date
                ),
            },
            tolerance={
                "future_days": (
                    future_tolerance_days
                ),
            },
            message=(
                "The invoice date is unreasonably "
                "future-dated."
            ),
            details={
                "evaluation_date": (
                    today.isoformat()
                ),
            },
        )

    if (
        context.due_date is not None
        and context.due_date
        < context.invoice_date
    ):
        return ValidationRuleResult(
            rule_id="VAL-05",
            rule_name="Date sanity",
            result="FAIL",
            blocking=True,
            expected_value={
                "due_date_not_before_invoice_date": True,
            },
            actual_value={
                "invoice_date": (
                    context.invoice_date.isoformat()
                ),
                "due_date": (
                    context.due_date.isoformat()
                ),
            },
            tolerance={
                "future_days": (
                    future_tolerance_days
                ),
            },
            message=(
                "The due date is before the "
                "invoice date."
            ),
            details={},
        )

    return ValidationRuleResult(
        rule_id="VAL-05",
        rule_name="Date sanity",
        result="PASS",
        blocking=False,
        expected_value={
            "latest_allowed_invoice_date": (
                future_limit.isoformat()
            ),
            "due_date_not_before_invoice_date": True,
        },
        actual_value={
            "invoice_date": (
                context.invoice_date.isoformat()
            ),
            "due_date": _date_text(
                context.due_date
            ),
        },
        tolerance={
            "future_days": (
                future_tolerance_days
            ),
        },
        message=(
            "Invoice and due dates satisfy "
            "the configured sanity rules."
        ),
        details={
            "evaluation_date": (
                today.isoformat()
            ),
        },
    )


def _validate_currency_consistency(
    context: InvoiceValidationContext,
    allowed_currencies: set[str],
) -> ValidationRuleResult:
    header_currency = (
        context.currency.upper()
        if context.currency
        else None
    )

    normalized_allowed = {
        value.upper()
        for value in allowed_currencies
    }

    if header_currency is None:
        return ValidationRuleResult(
            rule_id="VAL-06",
            rule_name="Currency consistency",
            result="FAIL",
            blocking=True,
            expected_value={
                "allowed_currencies": sorted(
                    normalized_allowed
                ),
                "line_currency_matches_header": True,
            },
            actual_value={
                "header_currency": None,
            },
            tolerance=None,
            message=(
                "The invoice header currency is missing."
            ),
            details={
                "scope": "header_and_lines",
            },
        )

    if (
        not re.fullmatch(
            r"[A-Z]{3}",
            header_currency,
        )
        or header_currency
        not in normalized_allowed
    ):
        return ValidationRuleResult(
            rule_id="VAL-06",
            rule_name="Currency consistency",
            result="FAIL",
            blocking=True,
            expected_value={
                "allowed_currencies": sorted(
                    normalized_allowed
                ),
                "line_currency_matches_header": True,
            },
            actual_value={
                "header_currency": (
                    header_currency
                ),
            },
            tolerance=None,
            message=(
                "The invoice header currency is not in "
                "the configured allow-list."
            ),
            details={
                "scope": "header_and_lines",
            },
        )

    if not context.line_items:
        return ValidationRuleResult(
            rule_id="VAL-06",
            rule_name="Currency consistency",
            result="WARNING",
            blocking=True,
            expected_value={
                "allowed_currencies": sorted(
                    normalized_allowed
                ),
                "line_currency_matches_header": True,
            },
            actual_value={
                "header_currency": (
                    header_currency
                ),
                "line_item_count": 0,
            },
            tolerance=None,
            message=(
                "Line-level currency consistency could "
                "not be proven because no line items "
                "were extracted."
            ),
            details={
                "scope": "header_and_lines",
            },
        )

    missing_currency_lines: list[int] = []
    mismatched_lines: list[dict] = []

    for item in context.line_items:
        if item.currency is None:
            missing_currency_lines.append(
                item.line_number
            )
            continue

        line_currency = (
            item.currency.upper()
        )

        if line_currency != header_currency:
            mismatched_lines.append(
                {
                    "line_number": (
                        item.line_number
                    ),
                    "description": (
                        item.description
                    ),
                    "header_currency": (
                        header_currency
                    ),
                    "line_currency": (
                        line_currency
                    ),
                }
            )

    if (
        missing_currency_lines
        or mismatched_lines
    ):
        return ValidationRuleResult(
            rule_id="VAL-06",
            rule_name="Currency consistency",
            result="FAIL",
            blocking=True,
            expected_value={
                "allowed_currencies": sorted(
                    normalized_allowed
                ),
                "header_currency": (
                    header_currency
                ),
                "line_currency_matches_header": True,
            },
            actual_value={
                "missing_currency_lines": (
                    missing_currency_lines
                ),
                "mismatched_lines": (
                    mismatched_lines
                ),
            },
            tolerance=None,
            message=(
                "One or more invoice lines have a "
                "missing or inconsistent currency."
            ),
            details={
                "scope": "header_and_lines",
            },
        )

    return ValidationRuleResult(
        rule_id="VAL-06",
        rule_name="Currency consistency",
        result="PASS",
        blocking=False,
        expected_value={
            "allowed_currencies": sorted(
                normalized_allowed
            ),
            "header_currency": (
                header_currency
            ),
            "line_currency_matches_header": True,
        },
        actual_value={
            "header_currency": (
                header_currency
            ),
            "line_currencies": [
                {
                    "line_number": (
                        item.line_number
                    ),
                    "currency": (
                        item.currency.upper()
                        if item.currency
                        else None
                    ),
                }
                for item in context.line_items
            ],
            "missing_currency_lines": [],
            "mismatched_lines": [],
        },
        tolerance=None,
        message=(
            "The header and all canonical line items "
            "use the same allowed currency."
        ),
        details={
            "scope": "header_and_lines",
        },
    )


def _validate_amount_sanity(
    context: InvoiceValidationContext,
) -> ValidationRuleResult:
    if context.total_amount is None:
        return ValidationRuleResult(
            rule_id="VAL-07",
            rule_name="Amount sanity",
            result="FAIL",
            blocking=True,
            expected_value={
                "total_amount": "greater_than_zero",
            },
            actual_value={
                "total_amount": None,
            },
            tolerance=None,
            message=(
                "The invoice total is missing."
            ),
            details={},
        )

    invalid_amounts: dict[str, str] = {}

    header_amounts = {
        "subtotal": context.subtotal,
        "discount_amount": (
            context.discount_amount
        ),
        "shipping_amount": (
            context.shipping_amount
        ),
        "tax_amount": context.tax_amount,
    }

    for field_name, amount in (
        header_amounts.items()
    ):
        if (
            amount is not None
            and amount < Decimal("0")
        ):
            invalid_amounts[field_name] = (
                _decimal_text(amount)
                or "0.00"
            )

    if context.total_amount <= Decimal("0"):
        invalid_amounts["total_amount"] = (
            _decimal_text(
                context.total_amount
            )
            or "0.00"
        )

    if invalid_amounts:
        return ValidationRuleResult(
            rule_id="VAL-07",
            rule_name="Amount sanity",
            result="FAIL",
            blocking=True,
            expected_value={
                "total_amount": "greater_than_zero",
                "header_amounts": "non_negative",
            },
            actual_value={
                "invalid_amounts": invalid_amounts,
            },
            tolerance=None,
            message=(
                "One or more invoice amounts violate "
                "the configured amount policy."
            ),
            details={
                "credit_note_policy": (
                    "route_to_review"
                ),
            },
        )

    return ValidationRuleResult(
        rule_id="VAL-07",
        rule_name="Amount sanity",
        result="PASS",
        blocking=False,
        expected_value={
            "total_amount": "greater_than_zero",
            "header_amounts": "non_negative",
        },
        actual_value={
            "subtotal": _decimal_text(
                context.subtotal
            ),
            "discount_amount": _decimal_text(
                context.discount_amount
            ),
            "shipping_amount": _decimal_text(
                context.shipping_amount
            ),
            "tax_amount": _decimal_text(
                context.tax_amount
            ),
            "total_amount": _decimal_text(
                context.total_amount
            ),
        },
        tolerance=None,
        message=(
            "Invoice header amounts satisfy "
            "the configured sanity policy."
        ),
        details={},
    )


def _validate_invoice_number_normalization(
    context: InvoiceValidationContext,
) -> ValidationRuleResult:
    if (
        context.raw_invoice_number is None
        or context.invoice_number is None
    ):
        return ValidationRuleResult(
            rule_id="VAL-08",
            rule_name="Invoice number normalization",
            result="FAIL",
            blocking=True,
            expected_value={
                "normalization": (
                    "trim whitespace, collapse spaces, "
                    "case-normalize and preserve separators"
                ),
            },
            actual_value={
                "raw_invoice_number": (
                    context.raw_invoice_number
                ),
                "canonical_invoice_number": (
                    context.invoice_number
                ),
            },
            tolerance=None,
            message=(
                "Invoice-number normalization cannot "
                "be proven because a value is missing."
            ),
            details={},
        )

    normalized_raw = normalize_invoice_number(
        context.raw_invoice_number
    )

    canonical = context.invoice_number

    passed = (
        normalized_raw == canonical
    )

    return ValidationRuleResult(
        rule_id="VAL-08",
        rule_name="Invoice number normalization",
        result=(
            "PASS"
            if passed
            else "FAIL"
        ),
        blocking=not passed,
        expected_value={
            "normalized_from_raw": normalized_raw,
            "separators_preserved": True,
        },
        actual_value={
            "raw_invoice_number": (
                context.raw_invoice_number
            ),
            "canonical_invoice_number": canonical,
        },
        tolerance=None,
        message=(
            "Invoice number is normalized without "
            "removing meaningful separators."
            if passed
            else (
                "The canonical invoice number does "
                "not match the approved normalization."
            )
        ),
        details={
            "normalization_version": (
                "invoice-number-v1"
            ),
        },
    )


def _decimal_text(
    value: Decimal | None,
) -> str | None:
    """
    Return stable monetary evidence with at least two decimals.
    """

    if value is None:
        return None

    fixed_value = format(
        value,
        "f",
    )

    if "." not in fixed_value:
        return f"{fixed_value}.00"

    whole_part, fraction_part = fixed_value.split(
        ".",
        1,
    )

    fraction_part = fraction_part.rstrip(
        "0"
    )

    if len(fraction_part) < 2:
        fraction_part = fraction_part.ljust(
            2,
            "0",
        )

    return f"{whole_part}.{fraction_part}"


def _date_text(
    value: date | None,
) -> str | None:
    return (
        value.isoformat()
        if value is not None
        else None
    )