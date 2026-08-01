# ADR-0010: Human Review Queue and Case Ownership

## Status

Accepted

## Context

The authoritative decision engine can route uncertain invoices to
`REVIEW_REQUIRED`.

Those decisions require an operational workflow where reviewers can find,
claim and investigate cases without losing ownership or history.

## Decision

A review case is created automatically whenever the authoritative decision
outcome is `REVIEW_REQUIRED`.

Only one active case may exist for a document.

Case states are:

- OPEN
- CLAIMED
- RESOLVED_APPROVED
- RESOLVED_REJECTED
- CANCELLED

This milestone implements OPEN and CLAIMED operations.

Any authenticated DocuFlow user can view the queue and add notes.

Only REVIEWER and ADMIN roles can claim cases.

A REVIEWER can release only a case claimed by that reviewer.

An ADMIN can release any claimed case.

Every lifecycle transition is stored as an immutable review-case event.

Priority is HIGH when a potential business duplicate is present and NORMAL
otherwise.

## Consequences

- Review-required invoices become operational work items.
- Two reviewers cannot silently claim the same open case.
- Case ownership is visible and auditable.
- Reviewer notes are preserved separately from invoice evidence.
- Correction and final-resolution actions can be added safely in the next
  milestone.