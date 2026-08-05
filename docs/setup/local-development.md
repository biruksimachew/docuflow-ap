# Local Development Setup

This guide starts DocuFlow AP on Windows PowerShell with Docker Desktop and local Supabase.

## 1. Prerequisites

Install:

- Git
- Docker Desktop with Linux containers
- Node.js 22 or newer
- npm
- PowerShell 7 or Windows PowerShell
- enough local disk space for Docker images and Supabase

The application services run in Docker. Supabase runs through the local Supabase CLI invoked with `npx`.

## 2. Clone and enter the repository

```powershell
git clone <repository-url>
Set-Location .\docuflow-ap
```

## 3. Create the local environment file

```powershell
Copy-Item `
    -LiteralPath .\.env.example `
    -Destination .\.env
```

Before provisioning users, set a local-only value for:

```text
DOCUFLOW_LOCAL_AUTH_PASSWORD
```

Do not commit `.env`.

## 4. Start local Supabase

Only one local Supabase project can own the default ports. Stop another local project before starting DocuFlow AP.

```powershell
npx supabase start `
    -x logflare,vector `
    --ignore-health-check
```

Expected local endpoints include:

- API: `http://127.0.0.1:54321`
- PostgreSQL: `127.0.0.1:54322`
- Studio: `http://127.0.0.1:54323`

## 5. Load local Supabase credentials safely

Run:

```powershell
powershell -ExecutionPolicy Bypass `
    -File scripts\configure_local_supabase.ps1
```

The script updates `.env` without printing the key values. It maps the local Supabase host to `host.docker.internal` so Docker containers can reach Auth and JWKS services.

## 6. Build and start application services

```powershell
docker compose up `
    --build `
    -d
```

Wait for startup, then inspect:

```powershell
docker compose ps -a
```

Expected state:

- `docuflow-api` — Up
- `docuflow-worker` — Up
- `docuflow-redis` — Up and healthy
- `docuflow-minio` — Up
- `docuflow-minio-init` — Exited `(0)` after creating buckets
- `docuflow-frontend` — Up

`minio-init` exiting with code `0` is expected.

## 7. Provision local authentication users

```powershell
docker compose exec -T api `
    python -m scripts.provision_local_auth_users
```

The idempotent script creates or updates:

| Role | Local email |
|---|---|
| AP Clerk | `ap.clerk@docuflow.local` |
| Reviewer | `reviewer.user@docuflow.local` |
| Administrator | `administrator@docuflow.local` |

All three use the password configured in `DOCUFLOW_LOCAL_AUTH_PASSWORD`.

## 8. Verify service health

```powershell
Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/health"
```

```powershell
Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/health/ready"
```

Both database and Redis must be ready.

## 9. Open the application

- Operations workspace: `http://127.0.0.1:31000`
- API documentation: `http://127.0.0.1:8000/docs`
- MinIO console: `http://127.0.0.1:9002`
- Supabase Studio: `http://127.0.0.1:54323`

Use `127.0.0.1` or `localhost` for the Next.js development site. Both origins are explicitly allowed in `frontend/next.config.ts`.

## 10. Run focused checks

```powershell
npm run typecheck `
    --prefix frontend
```

```powershell
npm run build `
    --prefix frontend
```

```powershell
docker compose exec -T api `
    pytest -q tests -p no:cacheprovider
```

```powershell
docker compose exec -T api `
    python -m scripts.check_frontend_dashboard
```

```powershell
docker compose exec -T api `
    python -m scripts.check_interactive_dashboard
```

## 11. Run the complete acceptance suite

```powershell
powershell -ExecutionPolicy Bypass `
    -File scripts\smoke_test.ps1
```

The final line must be:

```text
All DocuFlow AP dashboard-hardening checks passed.
```

## 12. Optional production frontend profile

Build and run the standalone Next.js production image:

```powershell
docker compose `
    --profile production `
    up `
    --build `
    -d `
    frontend-production
```

Open:

```text
http://127.0.0.1:31001
```

Demo authentication defaults to disabled for this profile.

## 13. Common troubleshooting

### Supabase database port is already allocated

Check for another Supabase project:

```powershell
docker ps `
    --filter publish=54322
```

Stop the other local Supabase project cleanly, then start DocuFlow AP again.

Do not delete Docker volumes as a first response to a port conflict.

### Authentication returns 401

Refresh `.env` from the running local Supabase instance:

```powershell
powershell -ExecutionPolicy Bypass `
    -File scripts\configure_local_supabase.ps1
```

Then recreate the API and frontend and reprovision users:

```powershell
docker compose up -d `
    --force-recreate `
    api frontend
```

```powershell
docker compose exec -T api `
    python -m scripts.provision_local_auth_users
```

### Frontend controls do not respond

Confirm the frontend logs do not report blocked development origins:

```powershell
docker compose logs `
    --tail=150 `
    frontend
```

Clear only generated Next.js state:

```powershell
docker compose stop frontend

Remove-Item `
    -LiteralPath .\frontend\.next `
    -Recurse `
    -Force `
    -ErrorAction SilentlyContinue

Remove-Item `
    -LiteralPath .\frontend\tsconfig.tsbuildinfo `
    -Force `
    -ErrorAction SilentlyContinue

docker compose up -d `
    --force-recreate `
    frontend
```

### API readiness reports database unavailable

Confirm local Supabase is running:

```powershell
npx supabase status
```

Then verify `DATABASE_URL` points from Docker to:

```text
host.docker.internal:54322
```

### MinIO console port

The S3 API uses port `9000`. The browser console uses port `9002`.
