create table if not exists public.review_corrections (
    id uuid primary key default gen_random_uuid(),

    review_case_id uuid not null
        references public.review_cases(id)
        on delete cascade,

    document_id uuid not null
        references public.documents(id)
        on delete cascade,

    target_type text not null
        check (
            target_type in (
                'HEADER',
                'LINE_ITEM'
            )
        ),

    line_item_id uuid
        references public.invoice_line_items(id)
        on delete restrict,

    field_name text not null,

    original_value jsonb,
    corrected_value jsonb,

    reason text not null,

    status text not null default 'PROPOSED'
        check (
            status in (
                'PROPOSED',
                'APPLIED',
                'REJECTED',
                'SUPERSEDED'
            )
        ),

    proposed_by_user_id uuid not null
        references public.app_user_roles(user_id)
        on delete restrict,

    proposed_by_email text not null,
    proposed_by_role text not null,
    proposed_at timestamptz not null default now(),

    applied_by_user_id uuid
        references public.app_user_roles(user_id)
        on delete restrict,

    applied_by_email text,
    applied_at timestamptz,

    rejected_by_user_id uuid
        references public.app_user_roles(user_id)
        on delete restrict,

    rejected_by_email text,
    rejected_at timestamptz,
    rejection_reason text,

    constraint review_correction_target_check
        check (
            (
                target_type = 'HEADER'
                and line_item_id is null
            )
            or
            (
                target_type = 'LINE_ITEM'
                and line_item_id is not null
            )
        )
);

create table if not exists public.review_control_runs (
    id uuid primary key default gen_random_uuid(),

    review_case_id uuid not null
        references public.review_cases(id)
        on delete cascade,

    document_id uuid not null
        references public.documents(id)
        on delete cascade,

    case_version integer not null
        check (case_version > 0),

    policy_version text not null
        default 'review-controls-v1',

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
                'PASSED',
                'REVIEW_REQUIRED',
                'BLOCKED'
            )
        ),

    validation_passed boolean,
    duplicate_outcome text,
    vendor_outcome text,
    po_outcome text,

    blocking_reasons jsonb
        not null default '[]'::jsonb,

    effective_snapshot jsonb
        not null default '{}'::jsonb,

    check_results jsonb
        not null default '{}'::jsonb,

    error_code text,
    error_message text,

    started_at timestamptz not null default now(),
    completed_at timestamptz
);

alter table public.review_cases
    add column if not exists latest_control_run_id uuid
        references public.review_control_runs(id)
        on delete set null;

alter table public.documents
    add column if not exists final_resolution_source text
        check (
            final_resolution_source is null
            or final_resolution_source in (
                'AUTOMATED',
                'MANUAL'
            )
        );

alter table public.documents
    add column if not exists manual_resolution_note text;

alter table public.documents
    add column if not exists manual_resolved_by_user_id uuid
        references public.app_user_roles(user_id)
        on delete set null;

alter table public.documents
    add column if not exists manual_resolved_by_email text;

alter table public.documents
    add column if not exists manual_resolved_at timestamptz;

alter table public.review_case_events
    drop constraint if exists
        review_case_events_event_type_check;

alter table public.review_case_events
    add constraint review_case_events_event_type_check
    check (
        event_type in (
            'CREATED',
            'CLAIMED',
            'RELEASED',
            'NOTE_ADDED',
            'CORRECTION_PROPOSED',
            'CORRECTION_APPLIED',
            'CORRECTION_REJECTED',
            'CONTROLS_RERUN',
            'RESOLVED_APPROVED',
            'RESOLVED_REJECTED',
            'CANCELLED'
        )
    );

create index if not exists
    idx_review_corrections_case
    on public.review_corrections (
        review_case_id,
        proposed_at
    );

create index if not exists
    idx_review_corrections_status
    on public.review_corrections (
        status,
        proposed_at
    );

create unique index if not exists
    idx_review_corrections_active_field
    on public.review_corrections (
        review_case_id,
        target_type,
        coalesce(
            line_item_id,
            '00000000-0000-0000-0000-000000000000'::uuid
        ),
        field_name
    )
    where status = 'APPLIED';

create index if not exists
    idx_review_control_runs_case
    on public.review_control_runs (
        review_case_id,
        started_at desc
    );

alter table public.review_corrections
    enable row level security;

alter table public.review_control_runs
    enable row level security;

comment on table public.review_corrections is
    'Audited correction overlay preserving original OCR and extraction evidence.';

comment on table public.review_control_runs is
    'Deterministic validation, duplicate, vendor and PO reruns over corrected invoice values.';