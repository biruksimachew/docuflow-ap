from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.core.config import settings
from app.security.models import AuthenticatedUser
from app.services.matching.engine import (
    evaluate_purchase_order_match,
    normalize_name,
    resolve_vendor_identity,
)
from app.services.matching.models import (
    InvoiceMatchInput,
    InvoiceMatchLine,
)
from app.services.matching.repository import (
    load_purchase_order,
    load_vendor_candidates,
)
from app.services.reviews.control_engine import (
    evaluate_effective_validation,
)
from app.services.reviews.correction_repository import (
    complete_review_control_run,
    fail_review_control_run,
    find_effective_business_duplicate,
    load_effective_invoice,
    start_review_control_run,
)


async def rerun_corrected_controls(
    *,
    review_case_id: str,
    actor: AuthenticatedUser,
) -> dict[str, Any]:
    run = await start_review_control_run(
        review_case_id=review_case_id
    )

    control_run_id = str(
        run["id"]
    )

    try:
        snapshot = await load_effective_invoice(
            review_case_id
        )

        header = snapshot[
            "effective"
        ]["header"]

        lines = snapshot[
            "effective"
        ]["lines"]

        tolerance = Decimal(
            str(
                settings
                .validation_currency_tolerance
            )
        )

        validation = (
            evaluate_effective_validation(
                header=header,
                lines=lines,
                tolerance=tolerance,
            )
        )

        duplicate = (
            await find_effective_business_duplicate(
                document_id=str(
                    snapshot[
                        "review_case"
                    ]["document_id"]
                ),
                vendor_name=header.get(
                    "vendor_name"
                ),
                invoice_number=header.get(
                    "invoice_number"
                ),
                invoice_date=header.get(
                    "invoice_date"
                ),
                currency=header.get(
                    "currency"
                ),
                total_amount=header.get(
                    "total_amount"
                ),
            )
        )

        normalized_vendor_name = (
            normalize_name(
                str(
                    header.get(
                        "vendor_name"
                    )
                )
            )
            if header.get(
                "vendor_name"
            )
            else ""
        )

        vendor_candidates = (
            await load_vendor_candidates(
                normalized_vendor_name
            )
            if normalized_vendor_name
            else ()
        )

        vendor_result = (
            resolve_vendor_identity(
                input_vendor_name=(
                    header.get(
                        "vendor_name"
                    )
                ),
                candidates=(
                    vendor_candidates
                ),
            )
        )

        purchase_order = await load_purchase_order(
            header.get(
                "purchase_order_number"
            )
        )

        invoice_lines = tuple(
            InvoiceMatchLine(
                line_number=int(
                    line[
                        "line_number"
                    ]
                ),
                description=str(
                    line.get(
                        "description"
                    )
                    or ""
                ),
                normalized_description=(
                    normalize_name(
                        str(
                            line.get(
                                "description"
                            )
                            or ""
                        )
                    )
                ),
                quantity=_decimal(
                    line.get(
                        "quantity"
                    )
                ),
                unit_price=_decimal(
                    line.get(
                        "unit_price"
                    )
                ),
                line_total=_decimal(
                    line.get(
                        "line_total"
                    )
                ),
            )
            for line in lines
        )

        invoice_input = InvoiceMatchInput(
            document_id=str(
                snapshot[
                    "review_case"
                ]["document_id"]
            ),
            invoice_extraction_id=str(
                snapshot[
                    "review_case"
                ]["invoice_extraction_id"]
            ),
            vendor_name=header.get(
                "vendor_name"
            ),
            purchase_order_number=(
                header.get(
                    "purchase_order_number"
                )
            ),
            currency=header.get(
                "currency"
            ),
            subtotal=_decimal(
                header.get(
                    "subtotal"
                )
            ),
            tax_amount=_decimal(
                header.get(
                    "tax_amount"
                )
            ),
            total_amount=_decimal(
                header.get(
                    "total_amount"
                )
            ),
            lines=invoice_lines,
        )

        po_result = (
            evaluate_purchase_order_match(
                invoice=invoice_input,
                resolved_vendor_id=(
                    vendor_result
                    .matched_vendor_id
                ),
                purchase_order=(
                    purchase_order
                ),
                tolerance=tolerance,
            )
        )

        blocking_reasons = list(
            validation[
                "blocking_reasons"
            ]
        )

        duplicate_outcome = duplicate[
            "outcome"
        ]

        if duplicate_outcome == "BUSINESS_DUPLICATE":
            blocking_reasons.append(
                "CONFIRMED_BUSINESS_DUPLICATE"
            )
        elif duplicate_outcome == "POTENTIAL_DUPLICATE":
            blocking_reasons.append(
                "POTENTIAL_BUSINESS_DUPLICATE"
            )

        if vendor_result.outcome != "MATCHED":
            blocking_reasons.append(
                f"VENDOR_{vendor_result.outcome}"
            )

        if po_result.outcome != "MATCHED":
            blocking_reasons.append(
                f"PURCHASE_ORDER_{po_result.outcome}"
            )

        blocking_reasons = list(
            dict.fromkeys(
                blocking_reasons
            )
        )

        if duplicate_outcome == "BUSINESS_DUPLICATE":
            outcome = "BLOCKED"
        elif blocking_reasons:
            outcome = "REVIEW_REQUIRED"
        else:
            outcome = "PASSED"

        check_results = {
            "validation": validation,
            "duplicate": duplicate,
            "vendor": {
                "outcome": (
                    vendor_result.outcome
                ),
                "blocking": (
                    vendor_result.blocking
                ),
                "matched_vendor_id": (
                    vendor_result
                    .matched_vendor_id
                ),
                "candidate_count": len(
                    vendor_result.candidates
                ),
                "evidence": (
                    vendor_result.evidence
                ),
            },
            "purchase_order": {
                "outcome": (
                    po_result.outcome
                ),
                "blocking": (
                    po_result.blocking
                ),
                "matched_purchase_order_id": (
                    po_result
                    .matched_purchase_order_id
                ),
                "matched_line_count": (
                    po_result
                    .matched_line_count
                ),
                "mismatched_line_count": (
                    po_result
                    .mismatched_line_count
                ),
                "checks": (
                    po_result.check_results
                ),
            },
        }

        completed = await complete_review_control_run(
            control_run_id=control_run_id,
            review_case_id=review_case_id,
            outcome=outcome,
            validation_passed=bool(
                validation["passed"]
            ),
            duplicate_outcome=(
                duplicate_outcome
            ),
            vendor_outcome=(
                vendor_result.outcome
            ),
            po_outcome=(
                po_result.outcome
            ),
            blocking_reasons=(
                blocking_reasons
            ),
            effective_snapshot=(
                snapshot
            ),
            check_results=(
                check_results
            ),
            actor=actor,
        )

        return completed

    except Exception as exc:
        await fail_review_control_run(
            control_run_id=control_run_id,
            error_code=type(exc).__name__,
            error_message=str(exc)[:2000],
        )

        raise


def _decimal(
    value: Any,
) -> Decimal | None:
    if value is None:
        return None

    return Decimal(
        str(value)
    )