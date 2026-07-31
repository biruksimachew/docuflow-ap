# ADR-0002: Deterministic Header Extraction

## Status

Accepted

## Context

DocuFlow AP must extract canonical invoice values while preserving raw OCR
output, normalized values, confidence and source-page evidence.

The MVP must remain operational without a paid LLM or cloud-document service.

## Decision

Header extraction uses deterministic label patterns, token layout and
normalization functions.

Each extracted field stores:

- Raw OCR value
- Normalized value
- Field confidence
- Confidence source
- Extraction method
- Page number
- Line text
- Bounding box
- Supporting OCR tokens
- Extraction-run reference

Typed canonical values are also stored in `invoice_headers` for downstream
validation, duplicate detection and purchase-order matching.

Invoice-number normalization trims and case-normalizes the value while
preserving meaningful separators.

A high OCR confidence does not make the extracted value authoritative.
Deterministic rules and authorized review decisions remain authoritative.

## Consequences

- Extraction behavior is reproducible and testable.
- Raw evidence remains available for audit and human review.
- The system runs without a paid AI provider.
- Additional template, cloud or vision-model extractors can be introduced
  behind the same persistence contract.
- Line-item extraction and final document confidence remain separate future
  milestones.