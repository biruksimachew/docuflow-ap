# ADR-0014: Next.js Operations Dashboard

## Status

Accepted

## Context

DocuFlow AP has a complete backend workflow, but portfolio users and
operations staff need a visual workspace that makes processing state,
exceptions and downstream activity immediately understandable.

The backend uses JWT authentication and database-authoritative application
roles. Browser code must not receive the Supabase JWT signing secret.

## Decision

The operations dashboard uses the Next.js App Router with TypeScript.

Next.js runs as a backend-for-frontend inside the Docker Compose network:

- Browser requests are same-origin to the Next.js application.
- Server Components call FastAPI through `http://api:8000`.
- The access token is stored in an HTTP-only, same-site cookie.
- The JWT signing secret is available only to the Next.js server process.
- Local demo login is explicitly controlled by
  `DOCUFLOW_DEMO_AUTH_ENABLED`.
- FastAPI remains authoritative for identity and role authorization.
- No browser-to-FastAPI CORS dependency is required.

The dashboard exposes:

- operational metrics
- recent invoice activity
- searchable invoice queue
- role-protected review queue
- invoice detail, control outcomes, exports and notification visibility

Dashboard read APIs are grouped under `/api/v1/dashboard`.

## Consequences

- Screenshots and demonstrations reflect live application data.
- Authentication secrets remain server-side.
- UI access follows the existing AP clerk, reviewer and administrator roles.
- The frontend can be deployed as a standalone Docker container.
- Future review actions can be added through the same backend-for-frontend
  pattern.
