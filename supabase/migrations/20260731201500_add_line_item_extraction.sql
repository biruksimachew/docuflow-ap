create table if not exists public.invoice_line_items (
    id uuid primary key default gen_random_uuid(),

    invoice_extraction_id uuid not null
        references public.invoice_extractions(id)
        on delete cascade,

    document_id uuid not null
        references public.documents(id)
        on delete cascade,

    line_number integer not null
        check (line_number > 0),

    description text not null,

    supplier_sku text,
    quantity numeric(18, 4),
    unit_of_measure text,
    unit_price numeric(18, 4),
    tax_rate numeric(9, 4),
    line_total numeric(18, 4),
    currency char(3),

    confidence numeric(5, 4) not null
        check (
            confidence >= 0
            and confidence <= 1
        ),

    confidence_source text not null,
    extraction_method text not null,

    page_number integer not null
        check (page_number > 0),

    raw_row_text text not null,

    normalized_values jsonb
        not null default '{}'::jsonb,

    field_evidence jsonb
        not null default '{}'::jsonb,

    row_evidence jsonb
        not null default '{}'::jsonb,

    created_at timestamptz not null default now(),

    unique (
        invoice_extraction_id,
        line_number
    )
);

alter table public.invoice_extractions
    add column if not exists line_item_count integer
        not null default 0
        check (line_item_count >= 0);

alter table public.invoice_extractions
    add column if not exists line_item_confidence
        numeric(5, 4)
        check (
            line_item_confidence is null
            or (
                line_item_confidence >= 0
                and line_item_confidence <= 1
            )
        );

alter table public.documents
    add column if not exists line_item_count integer
        not null default 0
        check (line_item_count >= 0);

alter table public.documents
    add column if not exists line_item_confidence
        numeric(5, 4)
        check (
            line_item_confidence is null
            or (
                line_item_confidence >= 0
                and line_item_confidence <= 1
            )
        );

create index if not exists
    idx_invoice_line_items_document
    on public.invoice_line_items (
        document_id,
        line_number
    );

create index if not exists
    idx_invoice_line_items_extraction
    on public.invoice_line_items (
        invoice_extraction_id,
        line_number
    );

alter table public.invoice_line_items
    enable row level security;

comment on table public.invoice_line_items is
    'Canonical invoice line items with raw OCR evidence, normalized values and confidence.';