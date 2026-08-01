# ADR-0009: Supabase Authentication and Role-Based Access Control

## Status

Accepted

## Context

DocuFlow AP now makes authoritative financial-processing decisions and exposes
invoice evidence through API endpoints.

Document evidence and future reviewer actions must not be accessible
anonymously.

## Decision

The API validates Supabase-compatible authenticated-user JWTs.

Validation includes:

- HS256 signature
- Expiration
- Audience
- UUID subject
- Authenticated end-user token role

The JWT establishes identity only.

The authoritative application role is loaded from `app_user_roles` using the
JWT subject. Application authorization is never trusted from an arbitrary
custom JWT claim.

Supported application roles are:

- AP_CLERK
- REVIEWER
- ADMIN

Current document evidence endpoints require any active DocuFlow role.

Reviewer capabilities require REVIEWER or ADMIN.

Administrative capabilities require ADMIN.

The upload endpoint remains available to approved machine and web intake
integrations. Existing intake signature, idempotency, file validation and
storage controls remain authoritative.

Authentication successes, failures and authorization denials are stored in
`security_audit_events`.

Local smoke tests use short-lived Supabase-compatible JWTs signed with the
local development JWT secret. Production and hosted environments must use the
actual Supabase project JWT secret and tokens issued by Supabase Auth.

## Consequences

- Anonymous users cannot read invoice evidence.
- A forged application-role claim cannot elevate privileges.
- Disabled or unprovisioned users cannot access DocuFlow.
- Reviewer and administrator boundaries are testable.
- Security events are auditable.
- Human review actions can now be implemented safely.