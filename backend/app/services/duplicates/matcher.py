from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from app.services.duplicates.models import (
    BusinessInvoiceIdentity,
    DuplicateCandidateEvaluation,
    DuplicateDetectionResult,
)


DUPLICATE_FIELDS = (
    "vendor_name",
    "invoice_number",
    "invoice_date",
    "currency",
    "total_amount",
)


def detect_business_duplicates(
    *,
    current: BusinessInvoiceIdentity,
    candidates: tuple[
        BusinessInvoiceIdentity,
        ...,
    ],
) -> DuplicateDetectionResult:
    """
    Compare the current canonical invoice with prior invoices.

    Vendor and invoice number form the candidate key. Date,
    currency and total distinguish exact from potential duplicates.
    """

    current_values = _normalized_values(
        current
    )

    evaluations: list[
        DuplicateCandidateEvaluation
    ] = []

    for candidate in candidates:
        candidate_values = _normalized_values(
            candidate
        )

        field_matches = {
            field_name: _same_present_value(
                current_values[field_name],
                candidate_values[field_name],
            )
            for field_name in DUPLICATE_FIELDS
        }

        candidate_key_matches = (
            field_matches["vendor_name"]
            and field_matches["invoice_number"]
        )

        if not candidate_key_matches:
            continue

        matched_field_count = sum(
            field_matches.values()
        )

        match_score = round(
            matched_field_count
            / len(DUPLICATE_FIELDS),
            4,
        )

        exact_match = all(
            field_matches.values()
        )

        evaluations.append(
            DuplicateCandidateEvaluation(
                candidate_document_id=(
                    candidate.document_id
                ),
                candidate_invoice_extraction_id=(
                    candidate.invoice_extraction_id
                ),
                outcome=(
                    "BUSINESS_DUPLICATE"
                    if exact_match
                    else "POTENTIAL_DUPLICATE"
                ),
                match_score=match_score,
                field_matches=field_matches,
                current_values=current_values,
                candidate_values=(
                    candidate_values
                ),
            )
        )

    evaluations.sort(
        key=lambda evaluation: (
            evaluation.outcome
            == "BUSINESS_DUPLICATE",
            evaluation.match_score,
            evaluation.candidate_document_id,
        ),
        reverse=True,
    )

    if any(
        evaluation.outcome
        == "BUSINESS_DUPLICATE"
        for evaluation in evaluations
    ):
        outcome = "BUSINESS_DUPLICATE"
        blocking = True
    elif evaluations:
        outcome = "POTENTIAL_DUPLICATE"
        blocking = True
    else:
        outcome = "CLEAR"
        blocking = False

    return DuplicateDetectionResult(
        outcome=outcome,
        blocking=blocking,
        input_fingerprint=current_values,
        candidates=tuple(evaluations),
    )


def normalize_vendor_name(
    value: str,
) -> str:
    normalized = re.sub(
        r"[\W_]+",
        " ",
        value.upper(),
        flags=re.UNICODE,
    )

    return re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()


def normalize_invoice_number(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        value.strip(),
    ).upper()


def _normalized_values(
    identity: BusinessInvoiceIdentity,
) -> dict[str, Any]:
    return {
        "vendor_name": (
            normalize_vendor_name(
                identity.vendor_name
            )
            if identity.vendor_name
            else None
        ),
        "invoice_number": (
            normalize_invoice_number(
                identity.invoice_number
            )
            if identity.invoice_number
            else None
        ),
        "invoice_date": (
            identity.invoice_date.isoformat()
            if identity.invoice_date
            else None
        ),
        "currency": (
            identity.currency.strip().upper()
            if identity.currency
            else None
        ),
        "total_amount": _decimal_text(
            identity.total_amount
        ),
    }


def _same_present_value(
    current_value: Any,
    candidate_value: Any,
) -> bool:
    return (
        current_value is not None
        and candidate_value is not None
        and current_value == candidate_value
    )


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