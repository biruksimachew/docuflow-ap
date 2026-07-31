from datetime import date
from decimal import Decimal

from app.services.validation.models import (
    InvoiceLineValidationItem,
    InvoiceValidationContext,
)
from app.services.validation.rules import (
    normalize_invoice_number,
    validate_invoice_header,
)


def create_line(
    *,
    line_number: int,
    description: str,
    quantity: str,
    unit_price: str,
    line_total: str,
    currency: str = "USD",
) -> InvoiceLineValidationItem:
    return InvoiceLineValidationItem(
        line_number=line_number,
        description=description,
        quantity=Decimal(
            quantity
        ),
        unit_price=Decimal(
            unit_price
        ),
        line_total=Decimal(
            line_total
        ),
        currency=currency,
    )


def default_lines() -> tuple[
    InvoiceLineValidationItem,
    ...,
]:
    return (
        create_line(
            line_number=1,
            description="Printer Paper",
            quantity="2",
            unit_price="50.00",
            line_total="100.00",
        ),
        create_line(
            line_number=2,
            description="Blue Pens",
            quantity="1",
            unit_price="20.00",
            line_total="20.00",
        ),
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
        "invoice_number": "INV-2001",
        "raw_invoice_number": "INV-2001",
        "invoice_date": date(
            2026,
            7,
            30,
        ),
        "due_date": None,
        "purchase_order_number": None,
        "currency": "USD",
        "subtotal": Decimal(
            "120.00"
        ),
        "discount_amount": None,
        "shipping_amount": None,
        "tax_amount": Decimal(
            "18.00"
        ),
        "total_amount": Decimal(
            "138.00"
        ),
        "line_items": default_lines(),
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


def validate(
    context: InvoiceValidationContext,
):
    return validate_invoice_header(
        context=context,
        allowed_currencies={
            "USD",
        },
        currency_tolerance=Decimal(
            "0.01"
        ),
        future_tolerance_days=7,
        today=date(
            2026,
            7,
            31,
        ),
    )


def test_clean_invoice_passes_all_controls() -> None:
    summary = validate(
        create_context()
    )

    assert (
        summary.overall_outcome
        == "PASSED_CONTROLS"
    )

    assert summary.blocking_count == 0
    assert summary.passed_count == 8
    assert summary.warning_count == 0
    assert summary.failed_count == 0

    results = result_map(
        summary
    )

    for rule_id in (
        "VAL-01",
        "VAL-02",
        "VAL-03",
        "VAL-04",
        "VAL-05",
        "VAL-06",
        "VAL-07",
        "VAL-08",
    ):
        assert (
            results[rule_id].result
            == "PASS"
        )

    assert (
        results["VAL-03"].actual_value[
            "difference"
        ]
        == "0.00"
    )

    line_results = results[
        "VAL-04"
    ].details["line_results"]

    assert len(
        line_results
    ) == 2

    assert all(
        line["result"] == "PASS"
        for line in line_results
    )


def test_header_arithmetic_mismatch_is_blocking() -> None:
    summary = validate(
        create_context(
            total_amount=Decimal(
                "140.00"
            )
        )
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

    assert (
        results["VAL-02"].result
        == "FAIL"
    )


def test_line_sum_mismatch_is_blocking() -> None:
    lines = (
        create_line(
            line_number=1,
            description="Printer Paper",
            quantity="2",
            unit_price="50.50",
            line_total="101.00",
        ),
        create_line(
            line_number=2,
            description="Blue Pens",
            quantity="1",
            unit_price="20.00",
            line_total="20.00",
        ),
    )

    summary = validate(
        create_context(
            line_items=lines
        )
    )

    results = result_map(
        summary
    )

    assert (
        results["VAL-03"].result
        == "FAIL"
    )

    assert (
        results["VAL-03"].blocking
        is True
    )

    assert (
        results["VAL-03"].actual_value[
            "calculated_line_sum"
        ]
        == "121.00"
    )

    assert (
        results["VAL-04"].result
        == "PASS"
    )


def test_line_arithmetic_mismatch_is_blocking() -> None:
    lines = (
        create_line(
            line_number=1,
            description="Printer Paper",
            quantity="2",
            unit_price="50.00",
            line_total="99.00",
        ),
        create_line(
            line_number=2,
            description="Blue Pens",
            quantity="1",
            unit_price="20.00",
            line_total="20.00",
        ),
    )

    summary = validate(
        create_context(
            subtotal=Decimal(
                "119.00"
            ),
            tax_amount=Decimal(
                "19.00"
            ),
            line_items=lines,
        )
    )

    results = result_map(
        summary
    )

    assert (
        results["VAL-03"].result
        == "PASS"
    )

    assert (
        results["VAL-04"].result
        == "FAIL"
    )

    assert (
        results["VAL-04"].actual_value[
            "failed_line_numbers"
        ]
        == [1]
    )


def test_currency_mismatch_is_blocking() -> None:
    lines = (
        create_line(
            line_number=1,
            description="Printer Paper",
            quantity="2",
            unit_price="50.00",
            line_total="100.00",
        ),
        create_line(
            line_number=2,
            description="Blue Pens",
            quantity="1",
            unit_price="20.00",
            line_total="20.00",
            currency="EUR",
        ),
    )

    summary = validate(
        create_context(
            line_items=lines
        )
    )

    results = result_map(
        summary
    )

    assert (
        results["VAL-06"].result
        == "FAIL"
    )

    assert (
        results["VAL-06"].blocking
        is True
    )

    mismatches = (
        results["VAL-06"]
        .actual_value[
            "mismatched_lines"
        ]
    )

    assert len(
        mismatches
    ) == 1

    assert (
        mismatches[0]["line_number"]
        == 2
    )


def test_missing_line_items_block_full_validation() -> None:
    summary = validate(
        create_context(
            line_items=()
        )
    )

    results = result_map(
        summary
    )

    assert (
        results["VAL-03"].result
        == "WARNING"
    )

    assert (
        results["VAL-04"].result
        == "WARNING"
    )

    assert (
        results["VAL-06"].result
        == "WARNING"
    )

    assert {
        "VAL-03",
        "VAL-04",
        "VAL-06",
    }.issubset(
        set(
            summary.blocking_rule_ids
        )
    )


def test_missing_total_and_invalid_due_date_fail() -> None:
    summary = validate(
        create_context(
            total_amount=None,
            due_date=date(
                2026,
                7,
                29,
            ),
        )
    )

    results = result_map(
        summary
    )

    assert (
        results["VAL-01"].result
        == "FAIL"
    )

    assert (
        results["VAL-05"].result
        == "FAIL"
    )

    assert (
        results["VAL-07"].result
        == "FAIL"
    )


def test_invoice_number_normalization_preserves_separators() -> None:
    assert (
        normalize_invoice_number(
            "  inv-2001 / a  "
        )
        == "INV-2001 / A"
    )

    summary = validate(
        create_context(
            invoice_number="INV-2001 / A",
            raw_invoice_number=(
                "  inv-2001 / a  "
            ),
        )
    )

    results = result_map(
        summary
    )

    assert (
        results["VAL-08"].result
        == "PASS"
    )