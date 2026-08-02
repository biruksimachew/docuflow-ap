create table if not exists public.accounting_exports (
    id uuid primary key default gen_random_uuid(),

    document_id uuid not null
        references public.documents(id)
        on delete cascade,

    review_case_id uuid
        references public.review_cases(id)
        on delete set null,

    decision_run_id uuid
        references public.decision_runs(id)
        on delete set null,

    export_format text not null
        check (
            export_format in (
                'JSON',
                'CSV'
            )
        ),

    schema_version text not null
        default 'accounting-export-v1',

    source_kind text not null
        check (
            source_kind in (
                'CANONICAL',
                'CORRECTED'
            )
        ),

    source_version text not null,

    idempotency_key text not null unique,

    status text not null default 'STARTED'
        check (
            status in (
                'STARTED',
                'READY',
                'FAILED'
            )
        ),

    file_name text,
    content_type text,
    payload_text text,
    payload_sha256 text,

    row_count integer
        check (
            row_count is null
            or row_count >= 0
        ),

    created_by_user_id uuid not null
        references public.app_user_roles(user_id)
        on delete restrict,

    created_by_email text not null,
    created_by_role text not null,

    requested_at timestamptz not null default now(),
    completed_at timestamptz,

    error_code text,
    error_message text,

    metadata jsonb
        not null default '{}'::jsonb
);

create table if not exists public.accounting_export_events (
    id uuid primary key default gen_random_uuid(),

    accounting_export_id uuid not null
        references public.accounting_exports(id)
        on delete cascade,

    document_id uuid not null
        references public.documents(id)
        on delete cascade,

    actor_user_id uuid not null
        references public.app_user_roles(user_id)
        on delete restrict,

    actor_email text not null,
    actor_role text not null,

    event_type text not null
        check (
            event_type in (
                'REQUESTED',
                'GENERATED',
                'DOWNLOADED',
                'FAILED'
            )
        ),

    message text not null,

    metadata jsonb
        not null default '{}'::jsonb,

    created_at timestamptz not null default now()
);

create index if not exists
    idx_accounting_exports_document
    on public.accounting_exports (
        document_id,
        requested_at desc
    );

create index if not exists
    idx_accounting_exports_status
    on public.accounting_exports (
        status,
        requested_at desc
    );

create index if not exists
    idx_accounting_export_events_export
    on public.accounting_export_events (
        accounting_export_id,
        created_at asc
    );

alter table public.accounting_exports
    enable row level security;

alter table public.accounting_export_events
    enable row level security;

comment on table public.accounting_exports is
    'Idempotent accounting-ready JSON and CSV invoice exports.';

comment on table public.accounting_export_events is
    'Immutable request, generation, download and failure audit history.';
