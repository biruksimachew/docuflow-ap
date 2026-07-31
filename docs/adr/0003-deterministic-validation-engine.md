# ADR-0003: Deterministic Validation Engine

## Status

Accepted

## Context

OCR confidence and extracted values cannot independently prove that an invoice
is safe for straight-through processing.

The approved requirements define deterministic controls for mandatory fields,
header arithmetic, date sanity, currency, amount policy and invoice-number
normalization.

## Decision

DocuFlow AP stores one versioned validation run for every canonical extraction.

Each rule result records:

- Rule ID and name
- PASS, WARNING or FAIL
- Whether the result blocks automated processing
- Expected value
- Actual value
- Configured tolerance
- Reviewer-readable message
- Structured diagnostic details
- Validation-run and document references
- Timestamp

Header arithmetic uses:

subtotal - discount + shipping + tax = total

Missing optional amount components are treated as zero only for arithmetic.
A missing subtotal or total prevents the arithmetic rule from being proven and
creates a blocking review result.

Invoice-number normalization trims whitespace, collapses repeated whitespace,
case-normalizes and preserves meaningful separators.

The current VAL-06 implementation validates the allowed header currency.
Line-level currency consistency will be completed with line-item extraction.

A high OCR or extraction confidence never overrides a blocking deterministic
result.

## Consequences

- Arithmetic mismatches retain expected, actual, difference and tolerance.
- Missing critical fields become visible blocking reasons.
- Validation decisions are reproducible and independently auditable.
- The document remains REVIEW_REQUIRED until line, duplicate, vendor and
  purchase-order controls are implemented.