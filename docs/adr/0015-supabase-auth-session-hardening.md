# ADR 0015: Supabase Authentication and Session Hardening

## Status

Accepted for Milestone 10B.1.

## Context

The Milestone 10A dashboard used server-generated demo JWTs so portfolio reviewers could explore each application role without credentials. The API already validated Supabase-compatible JWT signatures and loaded the authoritative DocuFlow role from `public.app_user_roles`.

Milestone 10B requires real user authentication without removing the useful portfolio demonstration path.

## Decision

DocuFlow AP uses Supabase Auth for email/password authentication.

The Next.js application acts as a backend-for-frontend boundary:

- credentials are posted only to a server route handler;
- the server exchanges credentials with Supabase Auth;
- access and refresh tokens are stored in HTTP-only, same-site cookies;
- `proxy.ts` performs an optimistic protected-route check and refreshes an expired Supabase session;
- every protected API request still sends the access token to FastAPI;
- FastAPI verifies the JWT and resolves the application role from PostgreSQL;
- API authorization remains authoritative and does not rely on the frontend proxy.

Local AP clerk, reviewer and administrator accounts are provisioned idempotently through the Supabase Auth admin API. The service-role key is used only inside the backend container and is never sent to the browser.

Demo role access remains available only when `DOCUFLOW_DEMO_AUTH_ENABLED=true`. Demo sessions do not receive refresh tokens.

## Consequences

- Real sign-in and refresh behavior can be exercised locally and in automated smoke tests.
- Production deployments can disable demo authentication without changing code.
- Session cookies require HTTPS in production.
- Local user provisioning must not be executed outside `APP_ENV=local`.
- The frontend dependency versions are pinned to prevent unreviewed framework upgrades.
