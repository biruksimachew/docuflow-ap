# ADR-0011: Audited Corrections and Review Resolution

## Status

Accepted

## Context

Review-required invoices need controlled correction and final-resolution
capabilities.

Changing the original OCR or extraction evidence would destroy the ability to
explain what the system originally observed.

Manual approval must also remain subject to deterministic controls.

## Decision

Corrections are stored as an overlay in `review_corrections`.

The original OCR tokens, extraction runs, canonical header and canonical line
items remain unchanged.

Correction states are:

- PROPOSED
- APPLIED
- REJECTED
- SUPERSEDED

AP_CLERK may propose corrections.

Only the claiming REVIEWER or an ADMIN may apply or reject corrections.

Applying a correction increments the review-case version and automatically
reruns:

- Required-field validation
- Header arithmetic
- Amount sanity
- Line arithmetic
- Line-total sum
- Currency consistency
- Business duplicate detection
- Vendor identity matching
- Purchase-order header and line matching

Each control run records the effective corrected snapshot, policy version,
individual checks, blocking reasons and case version.

Manual approval requires:

- A claimed review case
- The claiming reviewer or an administrator
- A current successful control run
- A control-run case version equal to the current case version
- Control outcome PASSED
- No confirmed business duplicate
- No technical processing failure

Manual rejection requires a claimed case and an auditable resolution note.

Resolved case states are:

- RESOLVED_APPROVED
- RESOLVED_REJECTED

The document stores the final manual resolution source, actor, note and
timestamp without replacing the original automated-decision evidence.

## Consequences

- Original machine evidence remains immutable.
- Corrections are attributable and reproducible.
- Stale control results cannot authorize approval.
- Confirmed duplicates cannot be manually approved.
- Reviewer actions are protected by role and ownership checks.
- The complete backend invoice workflow is operational.