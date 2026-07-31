# ADR-0004: Canonical Line-Item Extraction

## Status

Accepted

## Context

DocuFlow AP must extract invoice line items into a canonical schema while
retaining raw OCR evidence, normalized values and confidence.

The MVP must function without a paid document-intelligence provider.

## Decision

The first line-item extractor uses reconstructed OCR rows and a deterministic
numeric-tail pattern.

The canonical row supports:

- Description
- Supplier SKU
- Quantity
- Unit of measure
- Unit price
- Tax rate
- Line total
- Currency

The initial extractor requires description, quantity, unit price and line total.
Optional fields remain null when they are not explicitly available.

Each stored line preserves:

- Raw row text
- Normalized canonical values
- Row confidence
- Confidence source
- Extraction method
- Page number
- Bounding-box evidence
- Supporting OCR tokens
- Per-field raw and normalized evidence
- Invoice extraction reference

Currency can be explicit on the row or inherited from the canonical header.
Currency consistency remains subject to deterministic validation.

## Consequences

- Line extraction is deterministic and testable.
- The system remains operational without a paid AI provider.
- Missing or uncertain rows do not silently become authoritative values.
- VAL-03 line-sum validation and VAL-04 line arithmetic can now be implemented.
- Additional layout-aware and provider-specific extractors can be introduced
  behind the same persistence contract.