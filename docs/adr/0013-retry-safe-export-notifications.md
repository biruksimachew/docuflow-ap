# ADR-0013: Retry-Safe Export Notifications

## Status

Accepted

## Context

Ready accounting exports must be deliverable to downstream systems and
operations teams.

Network failures, duplicate requests and provider outages must not create
duplicate business events or erase attempt evidence.

## Decision

DocuFlow supports two notification channels:

- WEBHOOK
- EMAIL

Webhook delivery uses HTTP POST with:

- a stable delivery identifier
- a stable idempotency key
- the `accounting.export.ready` event name
- the accounting export payload
- an HMAC-SHA256 request signature
- a configured hostname allowlist

Email delivery uses a provider abstraction:

- `EMAIL_LOCAL_SINK` for deterministic local development and testing
- `EMAIL_SMTP` for deployed environments

A notification identity is derived from:

- template version
- accounting export identifier
- channel
- normalized destination hash

Repeated requests reuse the same notification delivery.

Delivery states are:

- PENDING
- DELIVERING
- RETRY_SCHEDULED
- SUCCEEDED
- FAILED

Every attempt is stored immutably with:

- attempt number
- request evidence
- response status and headers
- response-body excerpt
- retry classification
- retry delay
- error code and message
- start and completion timestamps

Retryable webhook outcomes include timeouts, network failures, HTTP 408,
HTTP 425, HTTP 429 and HTTP 5xx responses.

Retries use capped exponential delays.

A database row lock prevents concurrent tasks from creating duplicate
attempts for one delivery.

A stale-delivery timeout recovers jobs abandoned by a stopped worker while
preserving the interrupted attempt as failed evidence.

An administrator can requeue a non-successful delivery. Requeueing preserves
all previous attempt evidence and extends the allowed attempt count when
required.

Local tests use:

- an internal successful webhook sink
- an internal fail-once webhook sink
- a database-backed email sink

Production deployments must configure an appropriate webhook allowlist,
webhook signing secret and SMTP provider settings.

## Consequences

- Duplicate API requests do not create duplicate notification identities.
- Temporary provider failures recover automatically.
- Permanent failures remain visible and auditable.
- Downstream webhook consumers can verify payload integrity and origin.
- Email delivery can be tested without an external provider.
- Operations staff can inspect every delivery attempt.
