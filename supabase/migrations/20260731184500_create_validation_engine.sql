create table if not exists public.validation_runs (
    id uuid primary key default gen_random_uuid(),

    document_id uuid not null
        references public.documents(id)
        on delete cascade,

    processing_run_id uuid not null unique
        references public.processing_runs(id)
        on delete cascade,

    invoice_extraction_id uuid not null unique
        references public.invoice_extractions(id)
        on delete cascade,

    ruleset_version text not null default 'header-rules-v1',

    status text not null default 'STARTED'
        check (
            status in (
                'STARTED',
                'SUCCEEDED',
                'FAILED'
            )
        ),

    overall_outcome text
        check (
            overall_outcome is null
            or overall_outcome in (
                'PASSED_CONTROLS',
                'REVIEW_REQUIRED'
            )
        ),

    passed_count integer not null default 0
        check (passed_count >= 0),

    warning_count integer not null default 0
        check (warning_count >= 0),

    failed_count integer not null default 0
        check (failed_count >= 0),

    blocking_count integer not null default 0
        check (blocking_count >= 0),

    blocking_rule_ids jsonb
        not null default '[]'::jsonb,

    error_code text,
    error_message text,

    started_at timestamptz not null default now(),
    completed_at timestamptz
);

create table if not exists public.validation_results (
    id uuid primary key default gen_random_uuid(),

    validation_run_id uuid not null
        references public.validation_runs(id)
        on delete cascade,

    document_id uuid not null
        references public.documents(id)
        on delete cascade,

    rule_id text not null,
    rule_name text not null,

    result text not null
        check (
            result in (
                'PASS',
                'WARNING',
                'FAIL'
            )
        ),

    blocking boolean not null default false,

    expected_value jsonb,
    actual_value jsonb,
    tolerance jsonb,

    message text not null,
    details jsonb not null default '{}'::jsonb,

    created_at timestamptz not null default now(),

    unique (
        validation_run_id,
        rule_id
    )
);

alter table public.documents
    add column if not exists
        latest_validation_run_id uuid
        references public.validation_runs(id)
        on delete set null;

alter table public.documents
    add column if not exists validation_outcome text
        check (
            validation_outcome is null
            or validation_outcome in (
                'PASSED_CONTROLS',
                'REVIEW_REQUIRED'
            )
        );

alter table public.documents
    add column if not exists
        blocking_validation_count integer
        not null default 0
        check (
            blocking_validation_count >= 0
        );

create index if not exists
    idx_validation_runs_document
    on public.validation_runs (
        document_id,
        started_at desc
    );

create index if not exists
    idx_validation_results_run
    on public.validation_results (
        validation_run_id,
        rule_id
    );

create index if not exists
    idx_validation_results_document
    on public.validation_results (
        document_id,
        result,
        blocking
    );

alter table public.validation_runs
    enable row level security;

alter table public.validation_results
    enable row level security;

comment on table public.validation_runs is
    'Versioned deterministic validation execution for one extraction.';

comment on table public.validation_results is
    'Per-rule expected, actual, tolerance, result and review explanation.';