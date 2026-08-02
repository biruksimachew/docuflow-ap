# ADR-0012: Idempotent Accounting Exports

## Status

Accepted

## Context

Approved invoices must leave DocuFlow in an accounting-ready structure.

Repeated export requests must not produce conflicting artifacts, and every
request, generation and download must be auditable.

## Decision

DocuFlow produces two accounting export formats:

- JSON for system-to-system integrations
- CSV with one row per invoice line for spreadsheet and accounting imports

Only documents with status `AUTO_APPROVED` can be exported.

Automated approvals export the canonical extracted invoice.

Manually approved review cases export the effective corrected invoice overlay,
while preserving the original OCR and extraction evidence separately.

The export identity is derived from:

- schema version
- document identifier
- format
- source kind
- source version

This produces a deterministic idempotency key. Repeated requests for the same
source version and format reuse the existing export.

Each export preserves:

- source kind and source version
- decision or review-case reference
- original source filename and document digest
- content type and file name
- SHA-256 payload digest
- row count
- requesting user and role
- timestamps and failure details

CSV text cells that could be interpreted as spreadsheet formulas are escaped.

Immutable events record:

- REQUESTED
- GENERATED
- DOWNLOADED
- FAILED

## Consequences

- Approved invoices can be consumed by accounting tools.
- Repeated requests are safe.
- Corrected values are exported without mutating original evidence.
- Payload integrity can be verified.
- Spreadsheet formula injection is mitigated.
- Export access and download activity are auditable.
- Retry-safe notifications can reference stable export identifiers next.
