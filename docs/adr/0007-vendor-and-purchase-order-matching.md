# ADR-0007: Vendor and Purchase-Order Matching

## Status

Accepted

## Context

A canonical invoice cannot proceed toward automated approval until the
supplier identity and referenced purchase order are independently verified.

OCR confidence does not prove that a vendor exists or that an invoice agrees
with an authorized purchase order.

## Decision

Vendor identity resolution uses exact normalized matching against:

- Canonical vendor names
- Active vendor aliases

Vendor outcomes are:

- MATCHED
- UNMATCHED
- AMBIGUOUS

Only one unambiguous active match is accepted.

Purchase-order matching checks:

- PO number exists
- PO status is OPEN
- Resolved vendor matches the PO vendor
- Currency matches
- Subtotal matches within tolerance
- Tax matches within tolerance
- Total matches within tolerance
- Invoice and PO line counts match
- Description, quantity, unit price and line total match for every line

Purchase-order outcomes are:

- MATCHED
- NOT_PROVIDED
- NOT_FOUND
- VENDOR_UNRESOLVED
- MISMATCHED

Every non-matched outcome blocks automated approval.

All outcomes preserve expected values, actual values, differences, line-level
results, master-data references and run timestamps.

## Consequences

- Vendor identity is deterministic and auditable.
- Alias resolution is supported without silently rewriting OCR evidence.
- Purchase-order header and line discrepancies identify the exact failed check.
- Clean invoices now have all core evidence needed by the final decision engine.
- Human review, authenticated actions and export workflows remain pending.