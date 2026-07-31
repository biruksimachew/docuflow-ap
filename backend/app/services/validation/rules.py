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
    """Run the approved header-level deterministic controls."""

    evaluation_date = today or date.today()

    results = (
        _validate_required_fields(
            context
        ),
        _validate_header_arithmetic(
            context,
            currency_tolerance,
        ),
        _validate_date_sanity(
            context,
            evaluation_date,
            future_tolerance_days,
        ),
        _validate_currency(
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


def _validate_currency(
    context: InvoiceValidationContext,
    allowed_currencies: set[str],
) -> ValidationRuleResult:
    currency = (
        context.currency.upper()
        if context.currency
        else None
    )

    normalized_allowed = {
        value.upper()
        for value in allowed_currencies
    }

    if currency is None:
        return ValidationRuleResult(
            rule_id="VAL-06",
            rule_name="Currency consistency",
            result="FAIL",
            blocking=True,
            expected_value={
                "allowed_currencies": sorted(
                    normalized_allowed
                ),
            },
            actual_value={
                "header_currency": None,
            },
            tolerance=None,
            message=(
                "The invoice currency is missing."
            ),
            details={
                "scope": "header_only",
                "line_currency_check_pending": True,
            },
        )

    if (
        not re.fullmatch(
            r"[A-Z]{3}",
            currency,
        )
        or currency not in normalized_allowed
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
            },
            actual_value={
                "header_currency": currency,
            },
            tolerance=None,
            message=(
                "The invoice currency is not in "
                "the configured allow-list."
            ),
            details={
                "scope": "header_only",
                "line_currency_check_pending": True,
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
        },
        actual_value={
            "header_currency": currency,
        },
        tolerance=None,
        message=(
            "The header currency is valid and allowed."
        ),
        details={
            "scope": "header_only",
            "line_currency_check_pending": True,
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

    amounts_that_must_not_be_negative = {
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
        amounts_that_must_not_be_negative.items()
    ):
        if (
            amount is not None
            and amount < Decimal("0")
        ):
            invalid_amounts[field_name] = str(
                amount
            )

    if context.total_amount <= Decimal("0"):
        invalid_amounts["total_amount"] = str(
            context.total_amount
        )

    if invalid_amounts:
        return ValidationRuleResult(
            rule_id="VAL-07",
            rule_name="Amount sanity",
            result="FAIL",
            blocking=True,
            expected_value={
                "total_amount": "greater_than_zero",
                "header_amounts": (
                    "non_negative"
                ),
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
            "total_amount": str(
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
    Return stable monetary evidence with at least two decimal places.

    Database NUMERIC values may contain four scale digits, while currency
    evidence should remain consistent, such as 138.00 and 0.00.
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

    fraction_part = fraction_part.rstrip("0")

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