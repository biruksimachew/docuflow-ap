# Final Acceptance Checklist

Complete this checklist against the final release candidate before creating `v1.0.0`.

## Repository hygiene

- [ ] `git status --short` is clean before the release commit.
- [ ] `.env` is not tracked.
- [ ] Temporary installers, snapshots, ZIP files, and generated caches are removed or ignored.
- [ ] `git diff --check` reports no whitespace errors.
- [ ] README contains no stale milestone wording.
- [ ] ADR numbering is unique.
- [ ] No documentation claims XLSX export or another unimplemented capability.
- [ ] All portfolio disclosure language clearly states fictional/synthetic use.

## Clean local setup

- [ ] Local Supabase starts without another project owning ports `54321`–`54323`.
- [ ] `scripts/configure_local_supabase.ps1` updates `.env` without printing secrets.
- [ ] Docker Compose builds from the documented commands.
- [ ] API, worker, Redis, MinIO, and frontend reach the expected state.
- [ ] `minio-init` exits with code `0`.
- [ ] Local auth users provision idempotently.
- [ ] A second setup run does not create conflicting data or services.

## Security and access

- [ ] Anonymous access to protected invoice evidence is denied.
- [ ] Real Supabase email/password sign-in works.
- [ ] Access-token refresh works.
- [ ] Session cookies are HTTP-only and same-site.
- [ ] Demo authentication can be disabled through configuration.
- [ ] AP Clerk cannot perform reviewer-only actions.
- [ ] Reviewer cannot perform administrator-only notification retry.
- [ ] Application roles come from `app_user_roles`.
- [ ] HS256 test tokens and ES256/JWKS Supabase tokens validate as intended.
- [ ] Authentication failures and authorization denials are auditable.

## Intake and document pipeline

- [ ] PDF, JPEG, and PNG acceptance works.
- [ ] Invalid file content is rejected.
- [ ] Size and page-count limits are enforced.
- [ ] Exact duplicate upload reuses the existing document.
- [ ] Source object storage is available.
- [ ] Celery worker responds.
- [ ] Tesseract is installed.
- [ ] Preprocessing and OCR complete.
- [ ] Header extraction completes.
- [ ] Line-item extraction completes.
- [ ] Original OCR and extraction evidence remain immutable.

## Controls and decisions

- [ ] Header validation runs.
- [ ] Line validation runs.
- [ ] Currency/date/amount controls run.
- [ ] Business duplicate detection runs.
- [ ] Vendor identity matching runs.
- [ ] Purchase-order header/line matching runs.
- [ ] Auto-approval requires every policy condition.
- [ ] Confirmed duplicate produces rejection.
- [ ] Unproven approval conditions produce review.
- [ ] Technical failure is not mislabeled as business rejection.
- [ ] Decision explanation and reason codes are visible.

## Human review

- [ ] Review-required decision creates one active case.
- [ ] Reviewer can claim an open case.
- [ ] Ownership conflicts are rejected.
- [ ] Notes are retained.
- [ ] AP Clerk can propose a correction.
- [ ] Only the claiming reviewer or administrator can apply/reject a correction.
- [ ] Applying a correction increments case version.
- [ ] Rerun stores the effective corrected snapshot.
- [ ] Stale controls cannot authorize approval.
- [ ] Confirmed duplicate cannot be manually approved.
- [ ] Approval and rejection resolution are auditable.

## Exports and delivery

- [ ] JSON export generation works.
- [ ] CSV export generation works.
- [ ] Equivalent export requests reuse the same export.
- [ ] CSV formula-injection protection remains covered.
- [ ] Export download is audited.
- [ ] Webhook request includes stable ID, idempotency key, event name, and HMAC signature.
- [ ] Host allowlist is enforced.
- [ ] Email local sink works.
- [ ] Retryable failure schedules retry.
- [ ] Fail-once delivery eventually succeeds.
- [ ] Attempt history is immutable.
- [ ] Administrator requeue works for a non-successful delivery.

## Frontend

- [ ] Login controls hydrate and respond.
- [ ] Invalid credential error is visible.
- [ ] Real administrator login reaches the dashboard.
- [ ] Demo AP Clerk, Reviewer, and Administrator access works when enabled.
- [ ] Overview metrics render from live API/database state.
- [ ] Invoice search, filter, sorting, and pagination work.
- [ ] Review search, ownership filter, sorting, and pagination work.
- [ ] Document detail renders processing, extraction, controls, review, export, delivery, and audit information.
- [ ] Mutation feedback shows loading, success, and error states.
- [ ] High-impact actions request confirmation.
- [ ] AP Clerk and Reviewer interfaces hide unavailable navigation/actions.
- [ ] Production frontend image builds and starts.

## Automated validation

- [ ] `npm run typecheck --prefix frontend` passes.
- [ ] `npm run build --prefix frontend` passes.
- [ ] `pytest -q tests -p no:cacheprovider` passes.
- [ ] `python -m scripts.check_dashboard_api` passes.
- [ ] `python -m scripts.check_frontend_dashboard` passes.
- [ ] `python -m scripts.check_interactive_dashboard` passes.
- [ ] `python -m scripts.check_release_documentation` passes.
- [ ] `scripts\smoke_test.ps1` passes from beginning to end.

## Portfolio evidence

- [ ] Required screenshots are captured and sanitized.
- [ ] Full smoke output is stored.
- [ ] Typecheck and production-build output are stored.
- [ ] Repository hygiene evidence is stored.
- [ ] Demo video is 90–150 seconds.
- [ ] Evidence follows one coherent synthetic invoice story.
- [ ] No password, token, cookie, API key, personal data, or real financial data is visible.

## Release

- [ ] API and frontend release versions are intentionally chosen.
- [ ] `docs/release/v1.0.0-release-notes.md` matches the final candidate.
- [ ] `CHANGELOG.md` is updated with the release date.
- [ ] Final release commit is pushed.
- [ ] Annotated tag `v1.0.0` is created and pushed.
- [ ] GitHub release uses the approved release notes.
- [ ] Public repository README and evidence render correctly.
