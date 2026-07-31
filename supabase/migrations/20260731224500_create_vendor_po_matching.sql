create table if not exists public.vendors (
    id uuid primary key default gen_random_uuid(),

    vendor_code text not null unique,
    canonical_name text not null,
    normalized_name text not null,

    tax_identifier text,

    status text not null default 'ACTIVE'
        check (
            status in (
                'ACTIVE',
                'INACTIVE'
            )
        ),

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.vendor_aliases (
    id uuid primary key default gen_random_uuid(),

    vendor_id uuid not null
        references public.vendors(id)
        on delete cascade,

    alias_name text not null,
    normalized_alias text not null,

    active boolean not null default true,

    created_at timestamptz not null default now(),

    unique (
        vendor_id,
        normalized_alias
    )
);

create table if not exists public.purchase_orders (
    id uuid primary key default gen_random_uuid(),

    po_number text not null unique,

    vendor_id uuid not null
        references public.vendors(id)
        on delete restrict,

    currency char(3) not null,

    status text not null default 'OPEN'
        check (
            status in (
                'OPEN',
                'CLOSED',
                'CANCELLED'
            )
        ),

    subtotal numeric(18, 4) not null,
    tax_amount numeric(18, 4)
        not null default 0,
    total_amount numeric(18, 4) not null,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.purchase_order_lines (
    id uuid primary key default gen_random_uuid(),

    purchase_order_id uuid not null
        references public.purchase_orders(id)
        on delete cascade,

    line_number integer not null
        check (line_number > 0),

    description text not null,
    normalized_description text not null,

    quantity numeric(18, 4) not null,
    unit_price numeric(18, 4) not null,
    line_total numeric(18, 4) not null,

    created_at timestamptz not null default now(),

    unique (
        purchase_order_id,
        line_number
    )
);

create table if not exists public.vendor_match_runs (
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
        default 'vendor-identity-v1',

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
                'MATCHED',
                'UNMATCHED',
                'AMBIGUOUS'
            )
        ),

    blocking boolean not null default true,

    input_vendor_name text,
    normalized_input_name text,

    candidate_count integer not null default 0
        check (candidate_count >= 0),

    matched_vendor_id uuid
        references public.vendors(id)
        on delete set null,

    evidence jsonb
        not null default '{}'::jsonb,

    error_code text,
    error_message text,

    started_at timestamptz not null default now(),
    completed_at timestamptz
);

create table if not exists public.vendor_match_candidates (
    id uuid primary key default gen_random_uuid(),

    vendor_match_run_id uuid not null
        references public.vendor_match_runs(id)
        on delete cascade,

    vendor_id uuid not null
        references public.vendors(id)
        on delete cascade,

    vendor_code text not null,
    canonical_name text not null,

    matched_on text not null,
    match_score numeric(5, 4) not null
        check (
            match_score >= 0
            and match_score <= 1
        ),

    evidence jsonb
        not null default '{}'::jsonb,

    created_at timestamptz not null default now(),

    unique (
        vendor_match_run_id,
        vendor_id
    )
);

create table if not exists public.po_match_runs (
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

    vendor_match_run_id uuid
        references public.vendor_match_runs(id)
        on delete set null,

    ruleset_version text not null
        default 'purchase-order-v1',

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
                'MATCHED',
                'NOT_PROVIDED',
                'NOT_FOUND',
                'VENDOR_UNRESOLVED',
                'MISMATCHED'
            )
        ),

    blocking boolean not null default true,

    input_po_number text,

    matched_purchase_order_id uuid
        references public.purchase_orders(id)
        on delete set null,

    matched_line_count integer not null default 0
        check (matched_line_count >= 0),

    mismatched_line_count integer not null default 0
        check (mismatched_line_count >= 0),

    check_results jsonb
        not null default '{}'::jsonb,

    error_code text,
    error_message text,

    started_at timestamptz not null default now(),
    completed_at timestamptz
);

alter table public.documents
    add column if not exists
        latest_vendor_match_run_id uuid
        references public.vendor_match_runs(id)
        on delete set null;

alter table public.documents
    add column if not exists vendor_match_outcome text
        check (
            vendor_match_outcome is null
            or vendor_match_outcome in (
                'MATCHED',
                'UNMATCHED',
                'AMBIGUOUS'
            )
        );

alter table public.documents
    add column if not exists resolved_vendor_id uuid
        references public.vendors(id)
        on delete set null;

alter table public.documents
    add column if not exists
        latest_po_match_run_id uuid
        references public.po_match_runs(id)
        on delete set null;

alter table public.documents
    add column if not exists po_match_outcome text
        check (
            po_match_outcome is null
            or po_match_outcome in (
                'MATCHED',
                'NOT_PROVIDED',
                'NOT_FOUND',
                'VENDOR_UNRESOLVED',
                'MISMATCHED'
            )
        );

alter table public.documents
    add column if not exists
        matched_purchase_order_id uuid
        references public.purchase_orders(id)
        on delete set null;

alter table public.documents
    add column if not exists
        matching_blocking boolean
        not null default true;

create index if not exists
    idx_vendors_normalized_name
    on public.vendors (
        normalized_name
    );

create index if not exists
    idx_vendor_aliases_normalized_alias
    on public.vendor_aliases (
        normalized_alias
    );

create index if not exists
    idx_purchase_orders_vendor
    on public.purchase_orders (
        vendor_id,
        status
    );

create index if not exists
    idx_vendor_match_runs_document
    on public.vendor_match_runs (
        document_id,
        started_at desc
    );

create index if not exists
    idx_po_match_runs_document
    on public.po_match_runs (
        document_id,
        started_at desc
    );

drop trigger if exists
    trg_vendors_set_updated_at
    on public.vendors;

create trigger trg_vendors_set_updated_at
before update on public.vendors
for each row
execute function public.set_updated_at();

drop trigger if exists
    trg_purchase_orders_set_updated_at
    on public.purchase_orders;

create trigger trg_purchase_orders_set_updated_at
before update on public.purchase_orders
for each row
execute function public.set_updated_at();

alter table public.vendors
    enable row level security;

alter table public.vendor_aliases
    enable row level security;

alter table public.purchase_orders
    enable row level security;

alter table public.purchase_order_lines
    enable row level security;

alter table public.vendor_match_runs
    enable row level security;

alter table public.vendor_match_candidates
    enable row level security;

alter table public.po_match_runs
    enable row level security;

comment on table public.vendors is
    'Canonical supplier master used for deterministic invoice identity resolution.';

comment on table public.purchase_orders is
    'Purchase-order headers used for invoice-to-PO matching.';

comment on table public.po_match_runs is
    'Auditable purchase-order match execution with header and line evidence.';