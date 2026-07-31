create table if not exists public.decision_runs (
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

    validation_run_id uuid not null
        references public.validation_runs(id)
        on delete restrict,

    duplicate_check_id uuid not null
        references public.duplicate_checks(id)
        on delete restrict,

    vendor_match_run_id uuid not null
        references public.vendor_match_runs(id)
        on delete restrict,

    po_match_run_id uuid not null
        references public.po_match_runs(id)
        on delete restrict,

    policy_version text not null
        default 'invoice-decision-v1',

    status text not null default 'STARTED'
        check (
            status in (
                'STARTED',
                'SUCCEEDED',
                'FAILED'
            )
        ),

    outcome text
        check (
            outcome is null
            or outcome in (
                'AUTO_APPROVED',
                'REVIEW_REQUIRED',
                'REJECTED'
            )
        ),

    blocking boolean not null default true,

    reason_codes jsonb
        not null default '[]'::jsonb,

    explanation text,

    input_snapshot jsonb
        not null default '{}'::jsonb,

    threshold_snapshot jsonb
        not null default '{}'::jsonb,

    error_code text,
    error_message text,

    started_at timestamptz not null default now(),
    completed_at timestamptz
);

alter table public.documents
    add column if not exists
        latest_decision_run_id uuid
        references public.decision_runs(id)
        on delete set null;

alter table public.documents
    add column if not exists decision_outcome text
        check (
            decision_outcome is null
            or decision_outcome in (
                'AUTO_APPROVED',
                'REVIEW_REQUIRED',
                'REJECTED'
            )
        );

alter table public.documents
    add column if not exists decision_reason_codes jsonb
        not null default '[]'::jsonb;

alter table public.documents
    add column if not exists decision_explanation text;

alter table public.documents
    add column if not exists decided_at timestamptz;

create index if not exists
    idx_decision_runs_document
    on public.decision_runs (
        document_id,
        started_at desc
    );

create index if not exists
    idx_decision_runs_outcome
    on public.decision_runs (
        outcome,
        completed_at desc
    );

alter table public.decision_runs
    enable row level security;

comment on table public.decision_runs is
    'Versioned authoritative invoice decisions based on completed processing controls.';

do $$
declare
    constraint_record record;
begin
    for constraint_record in
        select constraint_item.conname
        from pg_constraint constraint_item
        where
            constraint_item.conrelid =
                'public.documents'::regclass
            and constraint_item.contype = 'c'
            and pg_get_constraintdef(
                constraint_item.oid
            ) ~* '\mstatus\M'
    loop
        execute format(
            'alter table public.documents drop constraint %I',
            constraint_record.conname
        );
    end loop;
end
$$;

alter table public.documents
    add constraint documents_status_check
    check (
        status in (
            'UPLOADED',
            'RECEIVED',
            'STORED',
            'QUEUED',
            'PROCESSING',
            'PREPROCESSING',
            'OCR_IN_PROGRESS',
            'EXTRACTION_IN_PROGRESS',
            'VALIDATING',
            'MATCHING',
            'DECIDING',
            'AUTO_APPROVED',
            'REVIEW_REQUIRED',
            'REJECTED',
            'FAILED'
        )
    );