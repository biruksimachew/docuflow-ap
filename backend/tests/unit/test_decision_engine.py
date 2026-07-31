from dataclasses import replace
from decimal import Decimal

from app.services.decisions.engine import (
    decide_invoice,
)
from app.services.decisions.models import (
    InvoiceDecisionInput,
)


def clean_input() -> InvoiceDecisionInput:
    return InvoiceDecisionInput(
        document_id="document-1",
        invoice_extraction_id="extraction-1",
        extraction_status="SUCCEEDED",
        header_confidence=Decimal(
            "0.9134"
        ),
        line_item_confidence=Decimal(
            "0.9015"
        ),
        line_item_count=2,
        validation_status="SUCCEEDED",
        validation_outcome=(
            "PASSED_CONTROLS"
        ),
        validation_blocking_count=0,
        duplicate_status="SUCCEEDED",
        duplicate_outcome="CLEAR",
        duplicate_blocking=False,
        vendor_match_status="SUCCEEDED",
        vendor_outcome="MATCHED",
        vendor_blocking=False,
        po_match_status="SUCCEEDED",
        po_outcome="MATCHED",
        po_blocking=False,
    )


def decide(
    decision_input: InvoiceDecisionInput,
):
    return decide_invoice(
        decision_input=decision_input,
        header_confidence_min=Decimal(
            "0.90"
        ),
        line_item_confidence_min=Decimal(
            "0.85"
        ),
    )


def test_clean_invoice_is_auto_approved() -> None:
    result = decide(
        clean_input()
    )

    assert (
        result.outcome
        == "AUTO_APPROVED"
    )

    assert result.blocking is False

    assert result.reason_codes == (
        "ALL_CONTROLS_PASSED",
    )


def test_confirmed_duplicate_is_rejected() -> None:
    result = decide(
        replace(
            clean_input(),
            duplicate_outcome=(
                "BUSINESS_DUPLICATE"
            ),
            duplicate_blocking=True,
        )
    )

    assert result.outcome == "REJECTED"
    assert result.blocking is True

    assert result.reason_codes == (
        "CONFIRMED_BUSINESS_DUPLICATE",
    )


def test_potential_duplicate_requires_review() -> None:
    result = decide(
        replace(
            clean_input(),
            duplicate_outcome=(
                "POTENTIAL_DUPLICATE"
            ),
            duplicate_blocking=True,
        )
    )

    assert (
        result.outcome
        == "REVIEW_REQUIRED"
    )

    assert (
        "POTENTIAL_BUSINESS_DUPLICATE"
        in result.reason_codes
    )


def test_low_confidence_requires_review() -> None:
    result = decide(
        replace(
            clean_input(),
            header_confidence=Decimal(
                "0.70"
            ),
        )
    )

    assert (
        result.outcome
        == "REVIEW_REQUIRED"
    )

    assert (
        "HEADER_CONFIDENCE_BELOW_THRESHOLD"
        in result.reason_codes
    )


def test_unmatched_vendor_and_po_require_review() -> None:
    result = decide(
        replace(
            clean_input(),
            vendor_outcome="UNMATCHED",
            vendor_blocking=True,
            po_outcome="VENDOR_UNRESOLVED",
            po_blocking=True,
        )
    )

    assert (
        result.outcome
        == "REVIEW_REQUIRED"
    )

    assert (
        "VENDOR_UNMATCHED"
        in result.reason_codes
    )

    assert (
        "PURCHASE_ORDER_VENDOR_UNRESOLVED"
        in result.reason_codes
    )


def test_failed_upstream_control_requires_review() -> None:
    result = decide(
        replace(
            clean_input(),
            validation_status="FAILED",
            validation_outcome=None,
            validation_blocking_count=1,
        )
    )

    assert (
        result.outcome
        == "REVIEW_REQUIRED"
    )

    assert (
        "VALIDATION_NOT_SUCCEEDED"
        in result.reason_codes
    )