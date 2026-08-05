# Changelog

All notable changes to DocuFlow AP are documented here.

## [Unreleased]

### Added

- Release-focused README and architecture documentation
- Local setup and troubleshooting guide
- Portfolio evidence capture plan
- Final acceptance checklist
- Draft `v1.0.0` release notes
- Release-documentation validation script
- Safe local Supabase environment configuration helper

### Changed

- Interactive operations workspace ADR renumbered to remove the duplicate ADR identifier

## [0.18.0] - 2026-08-05

### Added

- Real Supabase email/password authentication and refreshable HTTP-only sessions
- ES256/JWKS and HS256 JWT validation
- Database-authoritative AP clerk, reviewer, and administrator roles
- Protected Next.js operations workspace and same-origin API gateway
- Dashboard invoice and review search, filters, sorting, and pagination
- Review claim/release, notes, correction, control-rerun, and resolution actions
- Accounting export generation and download controls
- Notification-delivery visibility and administrator retry controls
- Interactive dashboard acceptance coverage

## [0.17.0] - 2026-08-03

### Added

- Next.js operations dashboard foundation
- Operations overview metrics
- Invoice and review queues
- Document detail visibility
- Demo-role sessions for portfolio review

## [0.16.0 and earlier]

### Added

- Secure/idempotent document intake
- Local Tesseract OCR and preprocessing
- Canonical header and line-item extraction
- Deterministic invoice validation
- Business duplicate detection
- Vendor identity and purchase-order matching
- Authoritative invoice decision policy
- Authentication and role-based authorization
- Human review ownership and audited corrections
- Idempotent JSON/CSV accounting exports
- Retry-safe webhook and email notification delivery
