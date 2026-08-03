import pytest
from fastapi import HTTPException

from app.api.routes.dashboard import (
    DOCUMENT_STATUSES,
    REVIEW_STATUSES,
)


def test_dashboard_document_statuses_cover_terminal_states() -> None:
    assert {
        "AUTO_APPROVED",
        "REVIEW_REQUIRED",
        "REJECTED",
        "FAILED",
    }.issubset(
        DOCUMENT_STATUSES
    )


def test_dashboard_review_statuses_cover_active_queue() -> None:
    assert {
        "OPEN",
        "CLAIMED",
    }.issubset(
        REVIEW_STATUSES
    )


def test_dashboard_status_sets_are_uppercase() -> None:
    assert all(
        value == value.upper()
        for value in DOCUMENT_STATUSES
    )

    assert all(
        value == value.upper()
        for value in REVIEW_STATUSES
    )


def test_status_sets_do_not_overlap_by_accident() -> None:
    assert "OPEN" not in DOCUMENT_STATUSES
    assert "AUTO_APPROVED" not in REVIEW_STATUSES
