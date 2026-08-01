create table if not exists public.review_cases (
    id uuid primary key default gen_random_uuid(),

    document_id uuid not null
        references public.documents(id)
        on delete cascade,

    decision_run_id uuid not null unique
        references public.decision_runs(id)
        on delete restrict,

    status text not null default 'OPEN'
        check (
            status in (
                'OPEN',
                'CLAIMED',
                'RESOLVED_APPROVED',
                'RESOLVED_REJECTED',
                'CANCELLED'
            )
        ),

    priority text not null default 'NORMAL'
        check (
            priority in (
                'NORMAL',
                'HIGH'
            )
        ),

    reason_codes jsonb
        not null default '[]'::jsonb,

    explanation text not null,

    claimed_by_user_id uuid
        references public.app_user_roles(user_id)
        on delete set null,

    claimed_by_email text,
    claimed_at timestamptz,

    resolved_by_user_id uuid
        references public.app_user_roles(user_id)
        on delete set null,

    resolved_by_email text,
    resolved_at timestamptz,

    resolution_note text,

    version integer not null default 1
        check (version > 0),

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.review_case_events (
    id uuid primary key default gen_random_uuid(),

    review_case_id uuid not null
        references public.review_cases(id)
        on delete cascade,

    document_id uuid not null
        references public.documents(id)
        on delete cascade,

    actor_type text not null
        check (
            actor_type in (
                'SYSTEM',
                'USER'
            )
        ),

    actor_user_id uuid
        references public.app_user_roles(user_id)
        on delete set null,

    actor_email text,
    actor_role text,

    event_type text not null
        check (
            event_type in (
                'CREATED',
                'CLAIMED',
                'RELEASED',
                'NOTE_ADDED',
                'RESOLVED_APPROVED',
                'RESOLVED_REJECTED',
                'CANCELLED'
            )
        ),

    message text not null,

    metadata jsonb
        not null default '{}'::jsonb,

    created_at timestamptz not null default now()
);

alter table public.documents
    add column if not exists latest_review_case_id uuid
        references public.review_cases(id)
        on delete set null;

create unique index if not exists
    idx_review_cases_one_active_per_document
    on public.review_cases (
        document_id
    )
    where status in (
        'OPEN',
        'CLAIMED'
    );

create index if not exists
    idx_review_cases_queue
    on public.review_cases (
        status,
        priority,
        created_at
    );

create index if not exists
    idx_review_cases_claimed_user
    on public.review_cases (
        claimed_by_user_id,
        status
    );

create index if not exists
    idx_review_case_events_case
    on public.review_case_events (
        review_case_id,
        created_at
    );

drop trigger if exists
    trg_review_cases_set_updated_at
    on public.review_cases;

create trigger trg_review_cases_set_updated_at
before update on public.review_cases
for each row
execute function public.set_updated_at();

alter table public.review_cases
    enable row level security;

alter table public.review_case_events
    enable row level security;

comment on table public.review_cases is
    'Human-review queue cases created from REVIEW_REQUIRED decisions.';

comment on table public.review_case_events is
    'Immutable ownership, note and resolution history for review cases.';