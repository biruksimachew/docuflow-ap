import pytest

from app.services.reviews.policy import (
    can_claim_review_case,
    can_release_review_case,
    normalize_review_note,
)


def test_reviewer_and_admin_can_claim() -> None:
    assert can_claim_review_case(
        "REVIEWER"
    )

    assert can_claim_review_case(
        "ADMIN"
    )


def test_clerk_cannot_claim() -> None:
    assert not can_claim_review_case(
        "AP_CLERK"
    )


def test_claiming_reviewer_can_release() -> None:
    assert can_release_review_case(
        actor_user_id="reviewer-1",
        actor_role="REVIEWER",
        claimed_by_user_id="reviewer-1",
    )


def test_another_reviewer_cannot_release() -> None:
    assert not can_release_review_case(
        actor_user_id="reviewer-2",
        actor_role="REVIEWER",
        claimed_by_user_id="reviewer-1",
    )


def test_admin_can_release_another_users_case() -> None:
    assert can_release_review_case(
        actor_user_id="admin-1",
        actor_role="ADMIN",
        claimed_by_user_id="reviewer-1",
    )


def test_review_note_is_normalized() -> None:
    assert normalize_review_note(
        "  Verify PO with procurement.  "
    ) == "Verify PO with procurement."


def test_empty_review_note_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        normalize_review_note(
            "   "
        )