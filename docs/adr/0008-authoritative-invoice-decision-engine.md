# ADR-0008: Authoritative Invoice Decision Engine

## Status

Accepted

## Context

DocuFlow AP now produces canonical extraction, deterministic validation,
business duplicate, vendor identity and purchase-order matching evidence.

The application requires one authoritative, versioned policy to convert those
independent controls into a final business outcome.

## Decision

The decision policy is versioned as `invoice-decision-v1`.

Possible outcomes are:

- AUTO_APPROVED
- REVIEW_REQUIRED
- REJECTED

A confirmed business duplicate produces REJECTED.

AUTO_APPROVED requires all of the following:

- Canonical extraction succeeded
- At least one canonical line item exists
- Header confidence meets the configured threshold
- Line-item confidence meets the configured threshold
- Deterministic validation succeeded with PASSED_CONTROLS
- Business duplicate detection succeeded with CLEAR
- Vendor identity succeeded with MATCHED
- Purchase-order matching succeeded with MATCHED
- No upstream control is blocking

Any non-rejection condition that cannot be proven produces REVIEW_REQUIRED.

Technical exceptions remain FAILED processing outcomes and are not converted
into business rejections.

Each decision stores:

- Policy version
- Final outcome
- Blocking state
- Machine-readable reason codes
- Reviewer-readable explanation
- Complete upstream input snapshot
- Applied threshold snapshot
- References to every authoritative control run
- Audit timestamp and event

## Consequences

- Automated approval is based on explicit policy rather than confidence alone.
- Confirmed duplicates are rejected consistently.
- Uncertain invoices remain recoverable through human review.
- Every final outcome can be explained and reproduced.
- The backend intelligence core is now ready for review workflow, authenticated
  actions, exports, alerts and the operations dashboard.