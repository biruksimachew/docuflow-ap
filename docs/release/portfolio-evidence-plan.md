# Portfolio Evidence Plan

The evidence package must prove business workflow, engineering controls, operator usability, and delivery discipline without exposing secrets or real financial information.

## 1. Evidence directory

```text
evidence/
├── screenshots/
├── recordings/
├── test-output/
└── README.md
```

Use PNG for screenshots and plain text for command output.

## 2. Naming convention

Use ordered filenames:

```text
01-login-and-roles.png
02-operations-overview.png
03-invoice-queue.png
04-invoice-extraction-evidence.png
05-control-outcomes.png
06-review-ownership.png
07-correction-and-rerun.png
08-accounting-export.png
09-delivery-attempts.png
10-audit-timeline.png
```

Test evidence:

```text
smoke-test-output.txt
frontend-typecheck.txt
frontend-production-build.txt
git-secret-hygiene.txt
```

Recording:

```text
docuflow-ap-demo.mp4
```

## 3. Required screenshots

### 01 — Login and role access

Role/context: signed out.

Capture:

- real email/password form;
- local account shortcuts;
- portfolio demo-role selector;
- AP Clerk, Reviewer, and Administrator choices.

Do not show a password.

### 02 — Operations overview

Role: Administrator.

Capture:

- total invoice count;
- auto-approved count and approval rate;
- review-required count;
- export/delivery health;
- latest invoice activity.

### 03 — Invoice queue

Role: AP Clerk or Administrator.

Capture:

- search input;
- status filter;
- sort field and direction;
- pagination;
- realistic synthetic vendor/invoice rows.

### 04 — Extraction evidence

Role: AP Clerk or Administrator.

Capture one synthetic invoice detail showing:

- source filename and digest context;
- vendor, invoice number, date, currency, subtotal, tax, and total;
- line items;
- confidence or evidence references;
- processing state.

### 05 — Deterministic controls

Role: Reviewer or Administrator.

Capture:

- header validation;
- line arithmetic;
- duplicate outcome;
- vendor identity result;
- purchase-order result;
- authoritative decision reason.

### 06 — Review ownership

Role: Reviewer.

Capture:

- review queue;
- ownership or assignee filter;
- claimed case;
- priority and reason;
- note history.

### 07 — Correction and rerun

Role: Reviewer or Administrator.

Capture:

- proposed correction;
- applied correction overlay;
- control rerun result;
- case-version relationship;
- approved or rejected resolution feedback.

### 08 — Accounting export

Role: AP Clerk, Reviewer, or Administrator.

Capture:

- JSON and CSV export options;
- generated export metadata;
- file name, digest, row count, and source version;
- download control.

### 09 — Delivery attempts

Role: Administrator.

Capture:

- webhook or email delivery;
- successful attempt;
- fail-once/retry evidence;
- final state;
- administrator retry control where applicable.

### 10 — Audit timeline

Role: Administrator.

Capture the chronological relationship between:

- intake;
- OCR/extraction;
- validation and matching;
- automated decision;
- case actions;
- corrections and reruns;
- resolution;
- export;
- delivery.

## 4. Command-output evidence

### Full acceptance suite

```powershell
powershell -ExecutionPolicy Bypass `
    -File scripts\smoke_test.ps1 `
    *>&1 |
    Tee-Object `
        -FilePath evidence\test-output\smoke-test-output.txt
```

Confirm the output ends with:

```text
All DocuFlow AP dashboard-hardening checks passed.
```

### Frontend typecheck

```powershell
npm run typecheck `
    --prefix frontend `
    *>&1 |
    Tee-Object `
        -FilePath evidence\test-output\frontend-typecheck.txt
```

### Frontend production build

```powershell
npm run build `
    --prefix frontend `
    *>&1 |
    Tee-Object `
        -FilePath evidence\test-output\frontend-production-build.txt
```

### Repository hygiene

Review staged paths and tracked environment files:

```powershell
@(
    "===== GIT STATUS =====",
    (git status --short),
    "",
    "===== TRACKED ENVIRONMENT FILES =====",
    (git ls-files "*env*" ".env*"),
    "",
    "===== RECENT COMMITS =====",
    (git log -8 --oneline)
) |
    Set-Content `
        -LiteralPath evidence\test-output\git-secret-hygiene.txt `
        -Encoding utf8
```

Manually inspect the result before publishing. Do not place secret values in evidence.

## 5. Demo video sequence

Target duration: 90–150 seconds.

### 0–15 seconds — Problem and outcome

Show the login or overview screen while explaining:

- invoices arrive as unstructured documents;
- AP teams need extraction, validation, matching, exception handling, and accounting-ready output;
- DocuFlow keeps deterministic controls and human accountability authoritative.

### 15–35 seconds — Intake and processing

Show:

- synthetic invoice intake;
- queued/background processing;
- OCR and canonical extraction result.

### 35–60 seconds — Controls and decision

Show:

- header/line validation;
- duplicate detection;
- vendor and purchase-order matching;
- `AUTO_APPROVED`, `REVIEW_REQUIRED`, or `REJECTED` explanation.

### 60–90 seconds — Human review

Show:

- reviewer claim;
- note;
- correction proposal;
- correction apply;
- control rerun;
- final resolution.

### 90–115 seconds — Export and delivery

Show:

- JSON or CSV export generation;
- idempotent reuse;
- webhook/email delivery;
- retry evidence.

### 115–135 seconds — Architecture and proof

Show:

- architecture diagram;
- full smoke-test pass;
- public repository structure.

End with the capabilities proved, not with a claim that the system is a deployed client product.

## 6. Sanitization rules

Before committing or publishing evidence:

- use synthetic invoice and purchase-order data only;
- hide passwords, tokens, cookies, API keys, SMTP credentials, and object-storage secrets;
- avoid browser developer-tool views containing authorization headers;
- hide local filesystem usernames where practical;
- do not expose service-role keys or Supabase status output;
- do not show real email inboxes or real vendor/customer records;
- inspect image metadata where necessary;
- confirm no `.env` file is tracked.

## 7. Evidence acceptance criteria

The package is ready when:

- every required screenshot is readable at normal viewing size;
- screenshots show one coherent synthetic business story;
- test outputs are from the final release candidate;
- the video follows the same invoice from intake through outcome;
- no evidence contradicts current code or README claims;
- no secret, personal data, or real financial record is visible.
