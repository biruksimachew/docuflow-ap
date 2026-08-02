from __future__ import annotations

from typing import Any

from app.security.models import AuthenticatedUser
from app.services.reviews.control_service import (
    rerun_corrected_controls,
)
from app.services.reviews.correction_policy import (
    normalize_correction_reason,
    normalize_correction_value,
    normalize_resolution_note,
)
from app.services.reviews.correction_repository import (
    apply_review_correction,
    create_review_correction,
    load_effective_invoice,
    reject_review_correction,
)


async def propose_correction(
    *,
    review_case_id: str,
    actor: AuthenticatedUser,
    target_type: str,
    line_item_id: str | None,
    field_name: str,
    corrected_value: Any,
    reason: str,
    apply_immediately: bool,
) -> dict[str, Any]:
    normalized_target = (
        target_type.strip().upper()
    )

    normalized_field = (
        field_name.strip()
    )

    normalized_value = (
        normalize_correction_value(
            target_type=normalized_target,
            field_name=normalized_field,
            value=corrected_value,
        )
    )

    normalized_reason = (
        normalize_correction_reason(
            reason
        )
    )

    snapshot = await load_effective_invoice(
        review_case_id
    )

    if normalized_target == "HEADER":
        if line_item_id is not None:
            raise ValueError(
                "Header corrections cannot include line_item_id."
            )

        effective_header = snapshot[
            "effective"
        ]["header"]

        original_value = (
            effective_header.get(
                normalized_field
            )
        )

    else:
        if line_item_id is None:
            raise ValueError(
                "Line-item corrections require line_item_id."
            )

        matching_line = next(
            (
                line
                for line in snapshot[
                    "effective"
                ]["lines"]
                if str(
                    line["id"]
                ) == line_item_id
            ),
            None,
        )

        if matching_line is None:
            raise ValueError(
                "The requested invoice line does not exist."
            )

        original_value = matching_line.get(
            normalized_field
        )

    correction = await create_review_correction(
        review_case_id=review_case_id,
        actor=actor,
        target_type=normalized_target,
        line_item_id=line_item_id,
        field_name=normalized_field,
        original_value=original_value,
        corrected_value=normalized_value,
        reason=normalized_reason,
    )

    control_run = None

    if apply_immediately:
        if actor.role not in {
            "REVIEWER",
            "ADMIN",
        }:
            raise PermissionError(
                "Only a reviewer or administrator can "
                "apply a correction immediately."
            )

        correction = await apply_review_correction(
            review_case_id=review_case_id,
            correction_id=str(
                correction["id"]
            ),
            actor=actor,
        )

        control_run = await rerun_corrected_controls(
            review_case_id=review_case_id,
            actor=actor,
        )

    return {
        "correction": correction,
        "control_run": control_run,
    }


async def apply_correction(
    *,
    review_case_id: str,
    correction_id: str,
    actor: AuthenticatedUser,
) -> dict[str, Any]:
    correction = await apply_review_correction(
        review_case_id=review_case_id,
        correction_id=correction_id,
        actor=actor,
    )

    control_run = await rerun_corrected_controls(
        review_case_id=review_case_id,
        actor=actor,
    )

    return {
        "correction": correction,
        "control_run": control_run,
    }


async def reject_correction(
    *,
    review_case_id: str,
    correction_id: str,
    actor: AuthenticatedUser,
    rejection_reason: str,
) -> dict[str, Any]:
    normalized_reason = (
        normalize_resolution_note(
            rejection_reason
        )
    )

    return await reject_review_correction(
        review_case_id=review_case_id,
        correction_id=correction_id,
        actor=actor,
        rejection_reason=(
            normalized_reason
        ),
    )