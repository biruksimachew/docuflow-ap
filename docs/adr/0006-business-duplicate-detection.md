# ADR-0006: Business Duplicate Detection

## Status

Accepted

## Context

File-hash idempotency prevents the same binary upload from being processed
twice, but it cannot detect rescanned, recompressed or reformatted copies of
the same business invoice.

DocuFlow AP therefore needs a deterministic duplicate identity based on
canonical invoice values.

## Decision

Business duplicate detection compares:

- Normalized vendor name
- Normalized invoice number
- Invoice date
- Currency
- Total amount

Vendor and invoice number form the candidate key.

An invoice is a `BUSINESS_DUPLICATE` when all five fields match a previous
canonical invoice.

An invoice is a `POTENTIAL_DUPLICATE` when vendor and invoice number match but
one or more of invoice date, currency or total differ or are unavailable.

Both outcomes block automated approval.

A `CLEAR` outcome means no previous candidate matched the vendor and invoice
number key.

Every candidate stores:

- Candidate document and extraction references
- Exact or potential outcome
- Match score
- Field-by-field match evidence
- Current canonical values
- Previous canonical values

## Consequences

- Different files representing the same invoice are detected.
- Duplicate reasoning is deterministic and auditable.
- Reviewers can see the exact matched invoice and fields.
- File idempotency and business duplicate detection remain separate controls.
- Vendor identity and purchase-order matching remain pending before final
  automated approval decisions.