# ADR-0005: Line-Level Deterministic Validation

## Status

Accepted

## Context

Canonical line items must not be trusted solely because OCR and extraction
confidence are high.

DocuFlow AP must prove that invoice rows reconcile mathematically and use the
same currency as the canonical header.

## Decision

The invoice validation ruleset is versioned as `invoice-rules-v2`.

The following line-level controls are authoritative:

- VAL-03: The sum of canonical line totals must equal the canonical subtotal.
- VAL-04: Quantity multiplied by unit price must equal line total for every row.
- VAL-06: Every line currency must match the allowed canonical header currency.

Each validation result stores:

- Expected values
- Actual values
- Calculated differences
- Currency tolerance
- Failed or incomplete line numbers
- Per-line diagnostic evidence
- Blocking status
- Reviewer-readable explanation

Missing line items or missing numeric values prevent the applicable rule from
being proven and create a blocking warning.

An arithmetic or currency mismatch creates a blocking failure.

OCR and extraction confidence never override these deterministic controls.

## Consequences

- Header and line mathematics are independently auditable.
- Reviewers can identify the exact failed line.
- Clean canonical invoices can proceed to duplicate, vendor and purchase-order
  controls.
- The system still cannot auto-approve until all business and matching controls
  are complete.