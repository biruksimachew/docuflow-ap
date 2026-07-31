from __future__ import annotations

from decimal import Decimal

from app.services.decisions.models import (
    InvoiceDecisionInput,
    InvoiceDecisionResult,
)


REASON_MESSAGES = {
    "ALL_CONTROLS_PASSED": (
        "All authoritative controls passed."
    ),
    "CONFIRMED_BUSINESS_DUPLICATE": (
        "The invoice exactly matches a previously "
        "processed business invoice."
    ),
    "EXTRACTION_NOT_SUCCEEDED": (
        "Canonical extraction did not complete successfully."
    ),
    "NO_LINE_ITEMS_EXTRACTED": (
        "No canonical invoice line items were extracted."
    ),
    "VALIDATION_NOT_SUCCEEDED": (
        "Deterministic validation did not complete successfully."
    ),
    "VALIDATION_CONTROLS_NOT_PASSED": (
        "One or more deterministic controls failed "
        "or could not be proven."
    ),
    "DUPLICATE_CHECK_NOT_SUCCEEDED": (
        "Business duplicate detection did not complete successfully."
    ),
    "POTENTIAL_BUSINESS_DUPLICATE": (
        "A possible business duplicate requires human review."
    ),
    "DUPLICATE_CHECK_NOT_CLEAR": (
        "Business duplicate detection did not produce a clear result."
    ),
    "VENDOR_MATCH_NOT_SUCCEEDED": (
        "Vendor identity matching did not complete successfully."
    ),
    "VENDOR_UNMATCHED": (
        "The supplier was not found in the vendor master."
    ),
    "VENDOR_AMBIGUOUS": (
        "More than one vendor-master record matches the supplier."
    ),
    "PURCHASE_ORDER_MATCH_NOT_SUCCEEDED": (
        "Purchase-order matching did not complete successfully."
    ),
    "PURCHASE_ORDER_NOT_PROVIDED": (
        "The invoice does not contain a purchase-order number."
    ),
    "PURCHASE_ORDER_NOT_FOUND": (
        "The referenced purchase order was not found."
    ),
    "PURCHASE_ORDER_VENDOR_UNRESOLVED": (
        "The purchase order cannot be approved until "
        "vendor identity is resolved."
    ),
    "PURCHASE_ORDER_MISMATCHED": (
        "The invoice does not fully match the purchase order."
    ),
    "HEADER_CONFIDENCE_MISSING": (
        "Header extraction confidence is unavailable."
    ),
    "HEADER_CONFIDENCE_BELOW_THRESHOLD": (
        "Header extraction confidence is below the approval threshold."
    ),
    "LINE_ITEM_CONFIDENCE_MISSING": (
        "Line-item extraction confidence is unavailable."
    ),
    "LINE_ITEM_CONFIDENCE_BELOW_THRESHOLD": (
        "Line-item extraction confidence is below the approval threshold."
    ),
}


def decide_invoice(
    *,
    decision_input: InvoiceDecisionInput,
    header_confidence_min: Decimal,
    line_item_confidence_min: Decimal,
) -> InvoiceDecisionResult:
    """
    Produce the authoritative business outcome.

    Confirmed business duplicates are rejected. All other incomplete,
    uncertain or blocking outcomes require review. Only a completely
    clean control set can be automatically approved.
    """

    header_threshold = _normalize_threshold(
        header_confidence_min
    )

    line_threshold = _normalize_threshold(
        line_item_confidence_min
    )

    input_snapshot = {
        "document_id": (
            decision_input.document_id
        ),
        "invoice_extraction_id": (
            decision_input.invoice_extraction_id
        ),
        "extraction_status": (
            decision_input.extraction_status
        ),
        "header_confidence": _decimal_text(
            decision_input.header_confidence
        ),
        "line_item_confidence": _decimal_text(
            decision_input.line_item_confidence
        ),
        "line_item_count": (
            decision_input.line_item_count
        ),
        "validation_status": (
            decision_input.validation_status
        ),
        "validation_outcome": (
            decision_input.validation_outcome
        ),
        "validation_blocking_count": (
            decision_input.validation_blocking_count
        ),
        "duplicate_status": (
            decision_input.duplicate_status
        ),
        "duplicate_outcome": (
            decision_input.duplicate_outcome
        ),
        "duplicate_blocking": (
            decision_input.duplicate_blocking
        ),
        "vendor_match_status": (
            decision_input.vendor_match_status
        ),
        "vendor_outcome": (
            decision_input.vendor_outcome
        ),
        "vendor_blocking": (
            decision_input.vendor_blocking
        ),
        "po_match_status": (
            decision_input.po_match_status
        ),
        "po_outcome": (
            decision_input.po_outcome
        ),
        "po_blocking": (
            decision_input.po_blocking
        ),
    }

    threshold_snapshot = {
        "header_confidence_min": _decimal_text(
            header_threshold
        ),
        "line_item_confidence_min": _decimal_text(
            line_threshold
        ),
    }

    if (
        decision_input.duplicate_status == "SUCCEEDED"
        and decision_input.duplicate_outcome
        == "BUSINESS_DUPLICATE"
    ):
        return InvoiceDecisionResult(
            outcome="REJECTED",
            blocking=True,
            reason_codes=(
                "CONFIRMED_BUSINESS_DUPLICATE",
            ),
            explanation=(
                "The invoice was rejected because it "
                "exactly matches a previously processed "
                "business invoice."
            ),
            input_snapshot=input_snapshot,
            threshold_snapshot=(
                threshold_snapshot
            ),
        )

    reason_codes: list[str] = []

    if (
        decision_input.extraction_status
        != "SUCCEEDED"
    ):
        reason_codes.append(
            "EXTRACTION_NOT_SUCCEEDED"
        )

    if decision_input.line_item_count <= 0:
        reason_codes.append(
            "NO_LINE_ITEMS_EXTRACTED"
        )

    if (
        decision_input.validation_status
        != "SUCCEEDED"
    ):
        reason_codes.append(
            "VALIDATION_NOT_SUCCEEDED"
        )
    elif (
        decision_input.validation_outcome
        != "PASSED_CONTROLS"
        or decision_input
        .validation_blocking_count > 0
    ):
        reason_codes.append(
            "VALIDATION_CONTROLS_NOT_PASSED"
        )

    if (
        decision_input.duplicate_status
        != "SUCCEEDED"
    ):
        reason_codes.append(
            "DUPLICATE_CHECK_NOT_SUCCEEDED"
        )
    elif (
        decision_input.duplicate_outcome
        == "POTENTIAL_DUPLICATE"
    ):
        reason_codes.append(
            "POTENTIAL_BUSINESS_DUPLICATE"
        )
    elif (
        decision_input.duplicate_outcome
        != "CLEAR"
        or decision_input.duplicate_blocking
    ):
        reason_codes.append(
            "DUPLICATE_CHECK_NOT_CLEAR"
        )

    if (
        decision_input.vendor_match_status
        != "SUCCEEDED"
    ):
        reason_codes.append(
            "VENDOR_MATCH_NOT_SUCCEEDED"
        )
    elif decision_input.vendor_outcome == "UNMATCHED":
        reason_codes.append(
            "VENDOR_UNMATCHED"
        )
    elif decision_input.vendor_outcome == "AMBIGUOUS":
        reason_codes.append(
            "VENDOR_AMBIGUOUS"
        )
    elif (
        decision_input.vendor_outcome
        != "MATCHED"
        or decision_input.vendor_blocking
    ):
        reason_codes.append(
            "VENDOR_UNMATCHED"
        )

    if (
        decision_input.po_match_status
        != "SUCCEEDED"
    ):
        reason_codes.append(
            "PURCHASE_ORDER_MATCH_NOT_SUCCEEDED"
        )
    elif decision_input.po_outcome == "NOT_PROVIDED":
        reason_codes.append(
            "PURCHASE_ORDER_NOT_PROVIDED"
        )
    elif decision_input.po_outcome == "NOT_FOUND":
        reason_codes.append(
            "PURCHASE_ORDER_NOT_FOUND"
        )
    elif (
        decision_input.po_outcome
        == "VENDOR_UNRESOLVED"
    ):
        reason_codes.append(
            "PURCHASE_ORDER_VENDOR_UNRESOLVED"
        )
    elif decision_input.po_outcome == "MISMATCHED":
        reason_codes.append(
            "PURCHASE_ORDER_MISMATCHED"
        )
    elif (
        decision_input.po_outcome
        != "MATCHED"
        or decision_input.po_blocking
    ):
        reason_codes.append(
            "PURCHASE_ORDER_MISMATCHED"
        )

    if decision_input.header_confidence is None:
        reason_codes.append(
            "HEADER_CONFIDENCE_MISSING"
        )
    elif (
        decision_input.header_confidence
        < header_threshold
    ):
        reason_codes.append(
            "HEADER_CONFIDENCE_BELOW_THRESHOLD"
        )

    if (
        decision_input.line_item_confidence
        is None
    ):
        reason_codes.append(
            "LINE_ITEM_CONFIDENCE_MISSING"
        )
    elif (
        decision_input.line_item_confidence
        < line_threshold
    ):
        reason_codes.append(
            "LINE_ITEM_CONFIDENCE_BELOW_THRESHOLD"
        )

    reason_codes = list(
        dict.fromkeys(
            reason_codes
        )
    )

    if reason_codes:
        explanation = (
            "The invoice requires human review: "
            + "; ".join(
                REASON_MESSAGES[reason_code]
                for reason_code in reason_codes
            )
        )

        return InvoiceDecisionResult(
            outcome="REVIEW_REQUIRED",
            blocking=True,
            reason_codes=tuple(
                reason_codes
            ),
            explanation=explanation,
            input_snapshot=input_snapshot,
            threshold_snapshot=(
                threshold_snapshot
            ),
        )

    return InvoiceDecisionResult(
        outcome="AUTO_APPROVED",
        blocking=False,
        reason_codes=(
            "ALL_CONTROLS_PASSED",
        ),
        explanation=(
            "The invoice was automatically approved "
            "because extraction, validation, duplicate, "
            "vendor, purchase-order and confidence "
            "controls all passed."
        ),
        input_snapshot=input_snapshot,
        threshold_snapshot=(
            threshold_snapshot
        ),
    )


def _normalize_threshold(
    value: Decimal,
) -> Decimal:
    if value < Decimal("0"):
        return Decimal("0")

    if value > Decimal("1"):
        return Decimal("1")

    return value


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