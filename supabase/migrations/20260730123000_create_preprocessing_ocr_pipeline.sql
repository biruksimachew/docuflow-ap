create table if not exists public.processing_runs (
    id uuid primary key default gen_random_uuid(),

    document_id uuid not null
        references public.documents(id)
        on delete cascade,

    attempt_number integer not null
        check (attempt_number > 0),

    status text not null default 'STARTED'
        check (
            status in (
                'STARTED',
                'SUCCEEDED',
                'FAILED'
            )
        ),

    error_code text,
    error_message text,

    started_at timestamptz not null default now(),
    completed_at timestamptz,

    unique (document_id, attempt_number)
);

alter table public.documents
    add column if not exists processing_attempts
        integer not null default 0;

alter table public.documents
    add column if not exists processing_started_at
        timestamptz;

alter table public.documents
    add column if not exists processing_completed_at
        timestamptz;

alter table public.documents
    add column if not exists last_error_code
        text;

alter table public.documents
    add column if not exists last_error_message
        text;

alter table public.documents
    add column if not exists last_processing_run_id
        uuid references public.processing_runs(id)
        on delete set null;

create table if not exists public.document_pages (
    id uuid primary key default gen_random_uuid(),

    processing_run_id uuid not null
        references public.processing_runs(id)
        on delete cascade,

    document_id uuid not null
        references public.documents(id)
        on delete cascade,

    page_number integer not null
        check (page_number > 0),

    original_storage_bucket text not null,
    original_storage_object_key text not null,

    processed_storage_bucket text not null,
    processed_storage_object_key text not null,

    width_px integer not null
        check (width_px > 0),

    height_px integer not null
        check (height_px > 0),

    preprocessing_operations jsonb
        not null default '[]'::jsonb,

    created_at timestamptz not null default now(),

    unique (processing_run_id, page_number)
);

create table if not exists public.ocr_runs (
    id uuid primary key default gen_random_uuid(),

    processing_run_id uuid not null unique
        references public.processing_runs(id)
        on delete cascade,

    document_id uuid not null
        references public.documents(id)
        on delete cascade,

    provider text not null,
    provider_version text not null,
    language text not null,

    status text not null default 'STARTED'
        check (
            status in (
                'STARTED',
                'SUCCEEDED',
                'FAILED'
            )
        ),

    error_code text,
    error_message text,

    started_at timestamptz not null default now(),
    completed_at timestamptz
);

create table if not exists public.ocr_page_results (
    id uuid primary key default gen_random_uuid(),

    ocr_run_id uuid not null
        references public.ocr_runs(id)
        on delete cascade,

    document_page_id uuid not null
        references public.document_pages(id)
        on delete cascade,

    page_number integer not null
        check (page_number > 0),

    raw_text text not null,

    average_confidence numeric(5, 4)
        check (
            average_confidence is null
            or (
                average_confidence >= 0
                and average_confidence <= 1
            )
        ),

    tokens jsonb not null default '[]'::jsonb,

    created_at timestamptz not null default now(),

    unique (ocr_run_id, page_number)
);

create index if not exists idx_processing_runs_document
    on public.processing_runs (
        document_id,
        attempt_number desc
    );

create index if not exists idx_document_pages_document
    on public.document_pages (
        document_id,
        page_number
    );

create index if not exists idx_ocr_runs_document
    on public.ocr_runs (
        document_id,
        started_at desc
    );

create index if not exists idx_ocr_page_results_run
    on public.ocr_page_results (
        ocr_run_id,
        page_number
    );

alter table public.processing_runs
    enable row level security;

alter table public.document_pages
    enable row level security;

alter table public.ocr_runs
    enable row level security;

alter table public.ocr_page_results
    enable row level security;

comment on table public.processing_runs is
    'Retry-safe document processing attempts.';

comment on table public.document_pages is
    'Original rendered and processed page artifacts for each attempt.';

comment on table public.ocr_runs is
    'OCR provider execution metadata.';

comment on table public.ocr_page_results is
    'Raw page text, confidence and token-level bounding-box evidence.';