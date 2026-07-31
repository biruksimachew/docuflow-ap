from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class BusinessInvoiceIdentity:
    """Canonical fields used for business duplicate detection."""

    document_id: str
    invoice_extraction_id: str

    vendor_name: str | None
    invoice_number: str | None
    invoice_date: date | None
    currency: str | None
    total_amount: Decimal | None


@dataclass(frozen=True)
class DuplicateCandidateEvaluation:
    """Field-by-field comparison with one previous invoice."""

    candidate_document_id: str
    candidate_invoice_extraction_id: str

    outcome: str
    match_score: float

    field_matches: dict[str, bool]
    current_values: dict[str, Any]
    candidate_values: dict[str, Any]


@dataclass(frozen=True)
class DuplicateDetectionResult:
    """Aggregated business duplicate decision."""

    outcome: str
    blocking: bool

    input_fingerprint: dict[str, Any]

    candidates: tuple[
        DuplicateCandidateEvaluation,
        ...,
    ]

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def exact_match_count(self) -> int:
        return sum(
            candidate.outcome
            == "BUSINESS_DUPLICATE"
            for candidate in self.candidates
        )

    @property
    def potential_match_count(self) -> int:
        return sum(
            candidate.outcome
            == "POTENTIAL_DUPLICATE"
            for candidate in self.candidates
        )

    @property
    def matched_document_id(self) -> str | None:
        if not self.candidates:
            return None

        return self.candidates[0].candidate_document_id

    @property
    def matched_invoice_extraction_id(
        self,
    ) -> str | None:
        if not self.candidates:
            return None

        return (
            self.candidates[0]
            .candidate_invoice_extraction_id
        )