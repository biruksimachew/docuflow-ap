create extension if not exists pgcrypto;

create table if not exists public.documents (
    id uuid primary key default gen_random_uuid(),

    status text not null default 'RECEIVED'
        check (
            status in (
                'RECEIVED',
                'FILE_VALIDATING',
                'QUARANTINED',
                'PREPROCESSING',
                'OCR_IN_PROGRESS',
                'EXTRACTION_IN_PROGRESS',
                'VALIDATING',
                'MATCHING',
                'AUTO_APPROVED',
                'REVIEW_REQUIRED',
                'APPROVED',
                'REJECTED',
                'EXPORT_READY',
                'EXPORTED',
                'FAILED',
                'RETRY_SCHEDULED'
            )
        ),

    source_channel text not null,

    original_filename text not null,
    sanitized_filename text not null,

    declared_media_type text,
    detected_media_type text not null,

    file_size_bytes bigint not null
        check (file_size_bytes > 0),

    page_count integer
        check (page_count is null or page_count > 0),

    sha256 text not null unique
        check (length(sha256) = 64),

    storage_provider text not null default 's3',
    storage_bucket text not null,
    storage_object_key text not null unique,

    quarantine_reason text,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_documents_status
    on public.documents (status);

create index if not exists idx_documents_created_at
    on public.documents (created_at desc);

create index if not exists idx_documents_source_channel
    on public.documents (source_channel);

create table if not exists public.document_sources (
    id uuid primary key default gen_random_uuid(),

    document_id uuid not null
        references public.documents(id)
        on delete cascade,

    source_channel text not null,
    source_message_id text,
    source_attachment_id text,

    source_metadata jsonb not null default '{}'::jsonb,

    created_at timestamptz not null default now()
);

create index if not exists idx_document_sources_document_id
    on public.document_sources (document_id);

create unique index if not exists uq_document_source_identity
    on public.document_sources (
        source_channel,
        source_message_id,
        source_attachment_id
    )
    where
        source_message_id is not null
        and source_attachment_id is not null;

create table if not exists public.audit_events (
    id bigint generated always as identity primary key,

    document_id uuid
        references public.documents(id)
        on delete cascade,

    event_type text not null,
    actor_type text not null default 'SYSTEM',
    actor_id text,

    reason text,
    payload jsonb not null default '{}'::jsonb,

    created_at timestamptz not null default now()
);

create index if not exists idx_audit_events_document_id_created_at
    on public.audit_events (
        document_id,
        created_at desc
    );

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_documents_set_updated_at
    on public.documents;

create trigger trg_documents_set_updated_at
before update on public.documents
for each row
execute function public.set_updated_at();

alter table public.documents enable row level security;
alter table public.document_sources enable row level security;
alter table public.audit_events enable row level security;

comment on table public.documents is
    'Canonical DocuFlow document record.';

comment on table public.document_sources is
    'Intake source identities associated with canonical documents.';

comment on table public.audit_events is
    'Append-only business and workflow event history.';