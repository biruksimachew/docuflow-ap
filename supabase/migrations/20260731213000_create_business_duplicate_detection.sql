create table if not exists public.duplicate_checks (
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

    ruleset_version text not null
        default 'business-duplicate-v1',

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
                'CLEAR',
                'POTENTIAL_DUPLICATE',
                'BUSINESS_DUPLICATE'
            )
        ),

    blocking boolean not null default false,

    candidate_count integer not null default 0
        check (candidate_count >= 0),

    exact_match_count integer not null default 0
        check (exact_match_count >= 0),

    potential_match_count integer not null default 0
        check (potential_match_count >= 0),

    matched_document_id uuid
        references public.documents(id)
        on delete set null,

    matched_invoice_extraction_id uuid
        references public.invoice_extractions(id)
        on delete set null,

    input_fingerprint jsonb
        not null default '{}'::jsonb,

    error_code text,
    error_message text,

    started_at timestamptz not null default now(),
    completed_at timestamptz
);

create table if not exists public.duplicate_candidates (
    id uuid primary key default gen_random_uuid(),

    duplicate_check_id uuid not null
        references public.duplicate_checks(id)
        on delete cascade,

    document_id uuid not null
        references public.documents(id)
        on delete cascade,

    candidate_document_id uuid not null
        references public.documents(id)
        on delete cascade,

    candidate_invoice_extraction_id uuid not null
        references public.invoice_extractions(id)
        on delete cascade,

    outcome text not null
        check (
            outcome in (
                'POTENTIAL_DUPLICATE',
                'BUSINESS_DUPLICATE'
            )
        ),

    match_score numeric(5, 4) not null
        check (
            match_score >= 0
            and match_score <= 1
        ),

    field_matches jsonb
        not null default '{}'::jsonb,

    current_values jsonb
        not null default '{}'::jsonb,

    candidate_values jsonb
        not null default '{}'::jsonb,

    created_at timestamptz not null default now(),

    unique (
        duplicate_check_id,
        candidate_invoice_extraction_id
    )
);

alter table public.documents
    add column if not exists
        latest_duplicate_check_id uuid
        references public.duplicate_checks(id)
        on delete set null;

alter table public.documents
    add column if not exists duplicate_outcome text
        check (
            duplicate_outcome is null
            or duplicate_outcome in (
                'CLEAR',
                'POTENTIAL_DUPLICATE',
                'BUSINESS_DUPLICATE'
            )
        );

alter table public.documents
    add column if not exists
        business_duplicate_blocking boolean
        not null default false;

alter table public.documents
    add column if not exists
        matched_duplicate_document_id uuid
        references public.documents(id)
        on delete set null;

create index if not exists
    idx_duplicate_checks_document
    on public.duplicate_checks (
        document_id,
        started_at desc
    );

create index if not exists
    idx_duplicate_candidates_check
    on public.duplicate_candidates (
        duplicate_check_id,
        match_score desc
    );

create index if not exists
    idx_duplicate_candidates_candidate_document
    on public.duplicate_candidates (
        candidate_document_id
    );

alter table public.duplicate_checks
    enable row level security;

alter table public.duplicate_candidates
    enable row level security;

comment on table public.duplicate_checks is
    'Deterministic business duplicate check using canonical invoice identity fields.';

comment on table public.duplicate_candidates is
    'Candidate invoices with field-by-field duplicate evidence and match score.';