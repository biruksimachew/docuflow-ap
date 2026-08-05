# DocuFlow AP Evidence

This directory contains sanitized portfolio evidence for the fictional DocuFlow AP implementation.

## Structure

- `screenshots/` — major operational flows
- `recordings/` — short product demonstration
- `test-output/` — final typecheck, build, smoke, and repository-hygiene output

Follow [`docs/release/portfolio-evidence-plan.md`](../docs/release/portfolio-evidence-plan.md) for required filenames, capture order, role context, and sanitization rules.

Do not add:

- `.env` files;
- tokens, passwords, cookies, or API keys;
- Supabase service-role output;
- real invoices, vendor records, purchase orders, or personal information;
- browser developer-tool captures containing authorization headers.
