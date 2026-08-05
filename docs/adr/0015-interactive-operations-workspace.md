# ADR 0015: Interactive Operations Workspace

## Status

Accepted

## Context

Milestone 10A exposed read-only dashboard views. Milestone 10B.1 added
real Supabase authentication, refreshable HTTP-only sessions, protected
routes and database-authoritative roles. Accounts-payable operators still
had to leave the dashboard or call APIs manually to claim cases, record
corrections, rerun controls, resolve reviews, generate exports and retry
failed deliveries.

The existing FastAPI routes already enforce business rules and role checks.
Duplicating those rules inside Next.js would create two authorization
systems and increase the risk of inconsistent decisions.

## Decision

The Next.js application uses a same-origin operations gateway under
`/api/operations/[...segments]`. The gateway:

- reads the HTTP-only access-token cookie on the server;
- forwards only allowlisted operations roots to FastAPI;
- preserves FastAPI status codes and error payloads;
- rejects cross-origin mutation requests;
- never exposes Supabase service-role credentials to the browser.

FastAPI remains authoritative for permissions, case ownership, correction
policy, control reruns, review resolution, accounting exports and delivery
retry rules.

Invoice and review queues use server-side filters, allowlisted sorting and
offset pagination. The document workspace uses client components only for
interactive controls; canonical state is refreshed from server-rendered
queries after each operation.

## Consequences

- Browser actions use the same audited backend contracts as direct API calls.
- Role and ownership failures remain consistent across UI and API clients.
- The dashboard can display immediate feedback without maintaining a second
  copy of invoice state.
- Offset pagination is sufficient for the portfolio dataset, but a larger
  deployment may replace it with cursor pagination.
- The generic gateway must remain allowlisted and same-origin protected.
