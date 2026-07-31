create table if not exists public.invoice_extractions (
    id uuid primary key default gen_random_uuid(),

    document_id uuid not null
        references public.documents(id)
        on delete cascade,

    processing_run_id uuid not null unique
        references public.processing_runs(id)
        on delete cascade,

    ocr_run_id uuid not null unique
        references public.ocr_runs(id)
        on delete cascade,

    schema_version text not null default 'header-v1',

    status text not null default 'STARTED'
        check (
            status in (
                'STARTED',
                'SUCCEEDED',
                'FAILED'
            )
        ),

    header_confidence numeric(5, 4)
        check (
            header_confidence is null
            or (
                header_confidence >= 0
                and header_confidence <= 1
            )
        ),

    extracted_field_count integer not null default 0
        check (extracted_field_count >= 0),

    missing_required_fields jsonb
        not null default '[]'::jsonb,

    error_code text,
    error_message text,

    started_at timestamptz not null default now(),
    completed_at timestamptz
);

create table if not exists public.extracted_fields (
    id uuid primary key default gen_random_uuid(),

    invoice_extraction_id uuid not null
        references public.invoice_extractions(id)
        on delete cascade,

    document_id uuid not null
        references public.documents(id)
        on delete cascade,

    field_name text not null,

    raw_value text not null,

    normalized_value jsonb not null,
    normalized_text text not null,

    confidence numeric(5, 4) not null
        check (
            confidence >= 0
            and confidence <= 1
        ),

    confidence_source text not null,
    extraction_method text not null,

    page_number integer not null
        check (page_number > 0),

    evidence jsonb not null,

    created_at timestamptz not null default now(),

    unique (
        invoice_extraction_id,
        field_name
    )
);

create table if not exists public.invoice_headers (
    id uuid primary key default gen_random_uuid(),

    invoice_extraction_id uuid not null unique
        references public.invoice_extractions(id)
        on delete cascade,

    document_id uuid not null
        references public.documents(id)
        on delete cascade,

    vendor_name text,
    invoice_number text,

    invoice_date date,
    due_date date,

    purchase_order_number text,
    currency char(3),

    subtotal numeric(18, 4),
    discount_amount numeric(18, 4),
    shipping_amount numeric(18, 4),
    tax_amount numeric(18, 4),
    total_amount numeric(18, 4),

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.documents
    add column if not exists header_confidence
        numeric(5, 4)
        check (
            header_confidence is null
            or (
                header_confidence >= 0
                and header_confidence <= 1
            )
        );

alter table public.documents
    add column if not exists
        latest_invoice_extraction_id uuid
        references public.invoice_extractions(id)
        on delete set null;

create index if not exists
    idx_invoice_extractions_document
    on public.invoice_extractions (
        document_id,
        started_at desc
    );

create index if not exists
    idx_extracted_fields_document
    on public.extracted_fields (
        document_id,
        field_name
    );

create index if not exists
    idx_extracted_fields_extraction
    on public.extracted_fields (
        invoice_extraction_id,
        field_name
    );

create index if not exists
    idx_invoice_headers_document
    on public.invoice_headers (
        document_id,
        created_at desc
    );

drop trigger if exists
    trg_invoice_headers_set_updated_at
    on public.invoice_headers;

create trigger trg_invoice_headers_set_updated_at
before update on public.invoice_headers
for each row
execute function public.set_updated_at();

alter table public.invoice_extractions
    enable row level security;

alter table public.extracted_fields
    enable row level security;

alter table public.invoice_headers
    enable row level security;

comment on table public.invoice_extractions is
    'Versioned canonical invoice extraction attempt linked to OCR evidence.';

comment on table public.extracted_fields is
    'Raw and normalized field values with confidence and page evidence.';

comment on table public.invoice_headers is
    'Typed canonical invoice header and amount values for downstream rules.';