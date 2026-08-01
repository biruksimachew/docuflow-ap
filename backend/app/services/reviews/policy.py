from __future__ import annotations


REVIEWER_ROLES = frozenset(
    {
        "REVIEWER",
        "ADMIN",
    }
)


def can_claim_review_case(
    role: str,
) -> bool:
    return role in REVIEWER_ROLES


def can_release_review_case(
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


def normalize_review_note(
    value: str,
) -> str:
    normalized = value.strip()

    if not normalized:
        raise ValueError(
            "A review note cannot be empty."
        )

    if len(normalized) > 2000:
        raise ValueError(
            "A review note cannot exceed 2000 characters."
        )

    return normalized