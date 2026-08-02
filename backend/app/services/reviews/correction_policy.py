from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any


HEADER_TEXT_FIELDS = frozenset(
    {
        "vendor_name",
        "invoice_number",
        "purchase_order_number",
        "currency",
    }
)

HEADER_DATE_FIELDS = frozenset(
    {
        "invoice_date",
        "due_date",
    }
)

HEADER_DECIMAL_FIELDS = frozenset(
    {
        "subtotal",
        "discount_amount",
        "shipping_amount",
        "tax_amount",
        "total_amount",
    }
)

LINE_TEXT_FIELDS = frozenset(
    {
        "description",
        "supplier_sku",
        "unit_of_measure",
        "currency",
    }
)

LINE_DECIMAL_FIELDS = frozenset(
    {
        "quantity",
        "unit_price",
        "tax_rate",
        "line_total",
    }
)


def normalize_correction_value(
    *,
    target_type: str,
    field_name: str,
    value: Any,
) -> Any:
    normalized_target = target_type.strip().upper()
    normalized_field = field_name.strip()

    if normalized_target == "HEADER":
        if normalized_field in HEADER_TEXT_FIELDS:
            return _text_value(
                value,
                uppercase=(
                    normalized_field
                    in {
                        "invoice_number",
                        "purchase_order_number",
                        "currency",
                    }
                ),
            )

        if normalized_field in HEADER_DATE_FIELDS:
            return _date_value(
                value
            )

        if normalized_field in HEADER_DECIMAL_FIELDS:
            return _decimal_value(
                value
            )

        raise ValueError(
            f"Unsupported header correction field: {normalized_field}"
        )

    if normalized_target == "LINE_ITEM":
        if normalized_field in LINE_TEXT_FIELDS:
            return _text_value(
                value,
                uppercase=(
                    normalized_field == "currency"
                ),
            )

        if normalized_field in LINE_DECIMAL_FIELDS:
            return _decimal_value(
                value
            )

        raise ValueError(
            f"Unsupported line-item correction field: {normalized_field}"
        )

    raise ValueError(
        "Correction target_type must be HEADER or LINE_ITEM."
    )


def normalize_correction_reason(
    value: str,
) -> str:
    normalized = value.strip()

    if len(normalized) < 5:
        raise ValueError(
            "A correction reason must contain at least 5 characters."
        )

    if len(normalized) > 1000:
        raise ValueError(
            "A correction reason cannot exceed 1000 characters."
        )

    return normalized


def normalize_resolution_note(
    value: str,
) -> str:
    normalized = value.strip()

    if len(normalized) < 10:
        raise ValueError(
            "A resolution note must contain at least 10 characters."
        )

    if len(normalized) > 2000:
        raise ValueError(
            "A resolution note cannot exceed 2000 characters."
        )

    return normalized


def can_manage_claimed_case(
    *,
    actor_user_id: str,
    actor_role: str,
    claimed_by_user_id: str | None,
) -> bool:
    if actor_role == "ADMIN":
        return True

    return (
        actor_role == "REVIEWER"
        and claimed_by_user_id
        == actor_user_id
    )


def approval_guard_reasons(
    *,
    document_status: str,
    case_version: int,
    control_case_version: int | None,
    control_status: str | None,
    control_outcome: str | None,
) -> tuple[str, ...]:
    reasons: list[str] = []

    if document_status == "FAILED":
        reasons.append(
            "DOCUMENT_PROCESSING_FAILED"
        )

    if control_case_version is None:
        reasons.append(
            "CONTROL_RERUN_REQUIRED"
        )
    elif control_case_version != case_version:
        reasons.append(
            "CONTROL_RERUN_STALE"
        )

    if control_status != "SUCCEEDED":
        reasons.append(
            "CONTROL_RERUN_NOT_SUCCEEDED"
        )

    if control_outcome != "PASSED":
        reasons.append(
            "CONTROL_RERUN_NOT_PASSED"
        )

    return tuple(
        dict.fromkeys(
            reasons
        )
    )


def _text_value(
    value: Any,
    *,
    uppercase: bool,
) -> str | None:
    if value is None:
        return None

    normalized = str(
        value
    ).strip()

    if not normalized:
        return None

    if uppercase:
        normalized = normalized.upper()

    return normalized


def _date_value(
    value: Any,
) -> str | None:
    if value is None:
        return None

    normalized = str(
        value
    ).strip()

    if not normalized:
        return None

    try:
        return date.fromisoformat(
            normalized
        ).isoformat()
    except ValueError as exc:
        raise ValueError(
            "Date corrections must use YYYY-MM-DD."
        ) from exc


def _decimal_value(
    value: Any,
) -> str | None:
    if value is None:
        return None

    normalized = str(
        value
    ).strip()

    if not normalized:
        return None

    try:
        decimal_value = Decimal(
            normalized
        )
    except InvalidOperation as exc:
        raise ValueError(
            "Numeric corrections must contain a valid decimal value."
        ) from exc

    if not decimal_value.is_finite():
        raise ValueError(
            "Numeric corrections must be finite."
        )

    return format(
        decimal_value,
        "f",
    )