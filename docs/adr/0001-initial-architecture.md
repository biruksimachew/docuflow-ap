# ADR-0001: Initial System Architecture

## Status

Accepted

## Context

DocuFlow AP requires dependable invoice intake, background document processing,
local OCR, deterministic validation, human review, exports, and complete auditability.

The MVP must remain operational without paid OCR or LLM services.

## Decision

The implementation will use:

- FastAPI for HTTP APIs and core business services.
- Celery and Redis for asynchronous processing, retries, and job isolation.
- Supabase PostgreSQL as the system of record.
- Supabase Auth for application identities and roles.
- Supabase Storage for original documents, derived page images, and exports.
- Next.js with TypeScript for the authenticated operations interface.
- Tesseract as the first local OCR provider.
- Docker Compose for repeatable local application services.

OCR providers will be accessed through a provider interface. OCR results may
suggest extracted values but cannot override deterministic validation rules.

n8n may be introduced later for email intake, alerts, and external workflow
integration. It will not become the authoritative invoice decision engine.

## Consequences

- Processing can be retried without creating additional document records.
- OCR providers can be replaced or compared without rewriting business rules.
- Original OCR output remains separate from human corrections.
- Deterministic rules remain authoritative.
- The application can run locally without a paid AI subscription.
