from datetime import date
from decimal import Decimal

from app.services.duplicates.matcher import (
    detect_business_duplicates,
)
from app.services.duplicates.models import (
    BusinessInvoiceIdentity,
)


def identity(
    *,
    document_id: str,
    vendor_name: str = (
        "Meridian Office Supplies"
    ),
    invoice_number: str = "INV-3001",
    invoice_date: date = date(
        2026,
        7,
        30,
    ),
    currency: str = "USD",
    total_amount: Decimal = Decimal(
        "138.00"
    ),
) -> BusinessInvoiceIdentity:
    return BusinessInvoiceIdentity(
        document_id=document_id,
        invoice_extraction_id=(
            f"{document_id}-extraction"
        ),
        vendor_name=vendor_name,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        currency=currency,
        total_amount=total_amount,
    )


def test_exact_business_duplicate_is_blocking() -> None:
    current = identity(
        document_id="current"
    )

    previous = identity(
        document_id="previous",
        vendor_name=(
            "MERIDIAN OFFICE SUPPLIES"
        ),
    )

    result = detect_business_duplicates(
        current=current,
        candidates=(previous,),
    )

    assert (
        result.outcome
        == "BUSINESS_DUPLICATE"
    )

    assert result.blocking is True
    assert result.exact_match_count == 1
    assert result.potential_match_count == 0

    candidate = result.candidates[0]

    assert candidate.match_score == 1.0
    assert all(
        candidate.field_matches.values()
    )


def test_same_vendor_and_number_with_changed_total_is_potential() -> None:
    current = identity(
        document_id="current"
    )

    previous = identity(
        document_id="previous",
        total_amount=Decimal(
            "140.00"
        ),
    )

    result = detect_business_duplicates(
        current=current,
        candidates=(previous,),
    )

    assert (
        result.outcome
        == "POTENTIAL_DUPLICATE"
    )

    assert result.blocking is True
    assert result.exact_match_count == 0
    assert result.potential_match_count == 1

    candidate = result.candidates[0]

    assert (
        candidate.field_matches[
            "total_amount"
        ]
        is False
    )


def test_same_invoice_number_for_different_vendor_is_clear() -> None:
    current = identity(
        document_id="current"
    )

    previous = identity(
        document_id="previous",
        vendor_name="Different Supplier",
    )

    result = detect_business_duplicates(
        current=current,
        candidates=(previous,),
    )

    assert result.outcome == "CLEAR"
    assert result.blocking is False
    assert result.candidate_count == 0