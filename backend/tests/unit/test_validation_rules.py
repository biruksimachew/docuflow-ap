from datetime import date
from decimal import Decimal

from app.services.validation.models import (
    InvoiceValidationContext,
)
from app.services.validation.rules import (
    normalize_invoice_number,
    validate_invoice_header,
)


def create_context(
    **overrides,
) -> InvoiceValidationContext:
    values = {
        "document_id": (
            "00000000-0000-0000-0000-000000000001"
        ),
        "invoice_extraction_id": (
            "00000000-0000-0000-0000-000000000002"
        ),
        "vendor_name": (
            "Meridian Office Supplies"
        ),
        "invoice_number": "INV-1001",
        "raw_invoice_number": "INV-1001",
        "invoice_date": date(
            2026,
            7,
            30,
        ),
        "due_date": None,
        "purchase_order_number": None,
        "currency": "USD",
        "subtotal": Decimal("120.00"),
        "discount_amount": None,
        "shipping_amount": None,
        "tax_amount": Decimal("18.00"),
        "total_amount": Decimal("138.00"),
    }

    values.update(
        overrides
    )

    return InvoiceValidationContext(
        **values
    )


def result_map(
    summary,
) -> dict:
    return {
        result.rule_id: result
        for result in summary.results
    }


def test_clean_header_passes_current_controls() -> None:
    summary = validate_invoice_header(
        context=create_context(),
        allowed_currencies={"USD"},
        currency_tolerance=Decimal("0.01"),
        future_tolerance_days=7,
        today=date(
            2026,
            7,
            31,
        ),
    )

    assert (
        summary.overall_outcome
        == "PASSED_CONTROLS"
    )

    assert summary.blocking_count == 0
    assert summary.passed_count == 6
    assert summary.warning_count == 0
    assert summary.failed_count == 0

    results = result_map(
        summary
    )

    assert results["VAL-01"].result == "PASS"
    assert results["VAL-02"].result == "PASS"
    assert results["VAL-05"].result == "PASS"
    assert results["VAL-06"].result == "PASS"
    assert results["VAL-07"].result == "PASS"
    assert results["VAL-08"].result == "PASS"

    assert (
        results["VAL-02"].actual_value[
            "difference"
        ]
        == "0.00"
    )


def test_header_arithmetic_mismatch_is_blocking() -> None:
    summary = validate_invoice_header(
        context=create_context(
            total_amount=Decimal("140.00")
        ),
        allowed_currencies={"USD"},
        currency_tolerance=Decimal("0.01"),
        future_tolerance_days=7,
        today=date(
            2026,
            7,
            31,
        ),
    )

    results = result_map(
        summary
    )

    assert (
        summary.overall_outcome
        == "REVIEW_REQUIRED"
    )

    assert "VAL-02" in (
        summary.blocking_rule_ids
    )

    assert results["VAL-02"].result == "FAIL"
    assert results["VAL-02"].blocking is True

    assert (
        results["VAL-02"].expected_value[
            "calculated_total"
        ]
        == "138.00"
    )

    assert (
        results["VAL-02"].actual_value[
            "stated_total"
        ]
        == "140.00"
    )


def test_missing_total_and_invalid_due_date_fail() -> None:
    summary = validate_invoice_header(
        context=create_context(
            total_amount=None,
            due_date=date(
                2026,
                7,
                29,
            ),
        ),
        allowed_currencies={"USD"},
        currency_tolerance=Decimal("0.01"),
        future_tolerance_days=7,
        today=date(
            2026,
            7,
            31,
        ),
    )

    results = result_map(
        summary
    )

    assert results["VAL-01"].result == "FAIL"
    assert results["VAL-05"].result == "FAIL"
    assert results["VAL-07"].result == "FAIL"

    assert {
        "VAL-01",
        "VAL-02",
        "VAL-05",
        "VAL-07",
    }.issubset(
        set(
            summary.blocking_rule_ids
        )
    )


def test_invoice_number_normalization_preserves_separators() -> None:
    assert (
        normalize_invoice_number(
            "  inv-1001 / a  "
        )
        == "INV-1001 / A"
    )

    summary = validate_invoice_header(
        context=create_context(
            invoice_number="INV-1001 / A",
            raw_invoice_number=(
                "  inv-1001 / a  "
            ),
        ),
        allowed_currencies={"USD"},
        currency_tolerance=Decimal("0.01"),
        future_tolerance_days=7,
        today=date(
            2026,
            7,
            31,
        ),
    )

    results = result_map(
        summary
    )

    assert results["VAL-08"].result == "PASS"