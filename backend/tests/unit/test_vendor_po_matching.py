from decimal import Decimal

from app.services.matching.engine import (
    evaluate_purchase_order_match,
    resolve_vendor_identity,
)
from app.services.matching.models import (
    InvoiceMatchInput,
    InvoiceMatchLine,
    PurchaseOrderLine,
    PurchaseOrderRecord,
    VendorCandidate,
)


def vendor_candidate(
    *,
    vendor_id: str = "vendor-1",
) -> VendorCandidate:
    return VendorCandidate(
        vendor_id=vendor_id,
        vendor_code="MERIDIAN-001",
        canonical_name=(
            "Meridian Office Supplies"
        ),
        normalized_name=(
            "MERIDIAN OFFICE SUPPLIES"
        ),
        matched_on="CANONICAL_NAME",
    )


def invoice_input(
    *,
    total_amount: str = "138.00",
    po_number: str | None = "PO-7001",
) -> InvoiceMatchInput:
    return InvoiceMatchInput(
        document_id="document-1",
        invoice_extraction_id=(
            "extraction-1"
        ),
        vendor_name=(
            "Meridian Office Supplies"
        ),
        purchase_order_number=(
            po_number
        ),
        currency="USD",
        subtotal=Decimal(
            "120.00"
        ),
        tax_amount=Decimal(
            "18.00"
        ),
        total_amount=Decimal(
            total_amount
        ),
        lines=(
            InvoiceMatchLine(
                line_number=1,
                description="Printer Paper",
                normalized_description=(
                    "PRINTER PAPER"
                ),
                quantity=Decimal("2"),
                unit_price=Decimal(
                    "50.00"
                ),
                line_total=Decimal(
                    "100.00"
                ),
            ),
            InvoiceMatchLine(
                line_number=2,
                description="Blue Pens",
                normalized_description=(
                    "BLUE PENS"
                ),
                quantity=Decimal("1"),
                unit_price=Decimal(
                    "20.00"
                ),
                line_total=Decimal(
                    "20.00"
                ),
            ),
        ),
    )


def purchase_order() -> PurchaseOrderRecord:
    return PurchaseOrderRecord(
        purchase_order_id="po-id-1",
        po_number="PO-7001",
        vendor_id="vendor-1",
        currency="USD",
        status="OPEN",
        subtotal=Decimal(
            "120.00"
        ),
        tax_amount=Decimal(
            "18.00"
        ),
        total_amount=Decimal(
            "138.00"
        ),
        lines=(
            PurchaseOrderLine(
                line_number=1,
                description="Printer Paper",
                normalized_description=(
                    "PRINTER PAPER"
                ),
                quantity=Decimal("2"),
                unit_price=Decimal(
                    "50.00"
                ),
                line_total=Decimal(
                    "100.00"
                ),
            ),
            PurchaseOrderLine(
                line_number=2,
                description="Blue Pens",
                normalized_description=(
                    "BLUE PENS"
                ),
                quantity=Decimal("1"),
                unit_price=Decimal(
                    "20.00"
                ),
                line_total=Decimal(
                    "20.00"
                ),
            ),
        ),
    )


def test_exact_vendor_identity_matches() -> None:
    candidate = vendor_candidate()

    result = resolve_vendor_identity(
        input_vendor_name=(
            "Meridian Office Supplies"
        ),
        candidates=(candidate,),
    )

    assert result.outcome == "MATCHED"
    assert result.blocking is False
    assert (
        result.matched_vendor_id
        == "vendor-1"
    )


def test_multiple_vendor_candidates_are_ambiguous() -> None:
    result = resolve_vendor_identity(
        input_vendor_name=(
            "Meridian Office Supplies"
        ),
        candidates=(
            vendor_candidate(
                vendor_id="vendor-1"
            ),
            vendor_candidate(
                vendor_id="vendor-2"
            ),
        ),
    )

    assert result.outcome == "AMBIGUOUS"
    assert result.blocking is True
    assert result.matched_vendor_id is None


def test_clean_invoice_matches_purchase_order() -> None:
    result = evaluate_purchase_order_match(
        invoice=invoice_input(),
        resolved_vendor_id="vendor-1",
        purchase_order=purchase_order(),
        tolerance=Decimal(
            "0.01"
        ),
    )

    assert result.outcome == "MATCHED"
    assert result.blocking is False
    assert result.matched_line_count == 2
    assert result.mismatched_line_count == 0

    checks = result.check_results

    assert checks[
        "purchase_order_status_open"
    ] is True

    assert checks[
        "vendor_matches"
    ] is True

    assert checks[
        "currency_matches"
    ] is True

    assert checks[
        "line_items_match"
    ] is True


def test_amount_mismatch_blocks_po_match() -> None:
    result = evaluate_purchase_order_match(
        invoice=invoice_input(
            total_amount="140.00"
        ),
        resolved_vendor_id="vendor-1",
        purchase_order=purchase_order(),
        tolerance=Decimal(
            "0.01"
        ),
    )

    assert result.outcome == "MISMATCHED"
    assert result.blocking is True

    assert (
        result.check_results[
            "total_amount"
        ]["matches"]
        is False
    )


def test_missing_po_number_is_blocking() -> None:
    result = evaluate_purchase_order_match(
        invoice=invoice_input(
            po_number=None
        ),
        resolved_vendor_id="vendor-1",
        purchase_order=None,
        tolerance=Decimal(
            "0.01"
        ),
    )

    assert (
        result.outcome
        == "NOT_PROVIDED"
    )

    assert result.blocking is True