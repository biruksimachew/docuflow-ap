from decimal import Decimal

import pytest

from app.services.reviews.control_engine import (
    evaluate_effective_validation,
)
from app.services.reviews.correction_policy import (
    approval_guard_reasons,
    can_manage_claimed_case,
    normalize_correction_value,
    normalize_resolution_note,
)


def clean_header() -> dict:
    return {
        "vendor_name": (
            "Meridian Office Supplies"
        ),
        "invoice_number": "INV-1001",
        "invoice_date": "2026-07-30",
        "purchase_order_number": "PO-7001",
        "currency": "USD",
        "subtotal": "120.00",
        "discount_amount": "0.00",
        "shipping_amount": "0.00",
        "tax_amount": "18.00",
        "total_amount": "138.00",
    }


def clean_lines() -> list[dict]:
    return [
        {
            "id": "line-1",
            "line_number": 1,
            "description": "Printer Paper",
            "quantity": "2",
            "unit_price": "50.00",
            "line_total": "100.00",
            "currency": "USD",
        },
        {
            "id": "line-2",
            "line_number": 2,
            "description": "Blue Pens",
            "quantity": "1",
            "unit_price": "20.00",
            "line_total": "20.00",
            "currency": "USD",
        },
    ]


def test_po_number_is_normalized() -> None:
    result = normalize_correction_value(
        target_type="HEADER",
        field_name="purchase_order_number",
        value=" po-7001 ",
    )

    assert result == "PO-7001"


def test_decimal_correction_is_normalized() -> None:
    result = normalize_correction_value(
        target_type="LINE_ITEM",
        field_name="unit_price",
        value="50.000",
    )

    assert result == "50.000"


def test_invalid_correction_field_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        normalize_correction_value(
            target_type="HEADER",
            field_name="bank_account",
            value="123",
        )


def test_claiming_reviewer_can_manage_case() -> None:
    assert can_manage_claimed_case(
        actor_user_id="reviewer-1",
        actor_role="REVIEWER",
        claimed_by_user_id="reviewer-1",
    )


def test_other_reviewer_cannot_manage_case() -> None:
    assert not can_manage_claimed_case(
        actor_user_id="reviewer-2",
        actor_role="REVIEWER",
        claimed_by_user_id="reviewer-1",
    )


def test_clean_corrected_invoice_passes_validation() -> None:
    result = evaluate_effective_validation(
        header=clean_header(),
        lines=clean_lines(),
        tolerance=Decimal(
            "0.01"
        ),
    )

    assert result["passed"] is True
    assert result["blocking_reasons"] == []


def test_line_mismatch_blocks_validation() -> None:
    lines = clean_lines()

    lines[0][
        "line_total"
    ] = "95.00"

    result = evaluate_effective_validation(
        header=clean_header(),
        lines=lines,
        tolerance=Decimal(
            "0.01"
        ),
    )

    assert result["passed"] is False

    assert (
        "LINE_ITEM_VALIDATION_FAILED"
        in result["blocking_reasons"]
    )


def test_stale_control_run_blocks_approval() -> None:
    reasons = approval_guard_reasons(
        document_status="REVIEW_REQUIRED",
        case_version=3,
        control_case_version=2,
        control_status="SUCCEEDED",
        control_outcome="PASSED",
    )

    assert (
        "CONTROL_RERUN_STALE"
        in reasons
    )


def test_current_passed_control_run_allows_approval() -> None:
    reasons = approval_guard_reasons(
        document_status="REVIEW_REQUIRED",
        case_version=3,
        control_case_version=3,
        control_status="SUCCEEDED",
        control_outcome="PASSED",
    )

    assert reasons == ()


def test_resolution_note_is_required() -> None:
    with pytest.raises(
        ValueError
    ):
        normalize_resolution_note(
            "too short"
        )