create table if not exists public.notification_deliveries (
    id uuid primary key default gen_random_uuid(),

    accounting_export_id uuid not null
        references public.accounting_exports(id)
        on delete cascade,

    document_id uuid not null
        references public.documents(id)
        on delete cascade,

    channel text not null
        check (
            channel in (
                'WEBHOOK',
                'EMAIL'
            )
        ),

    provider text not null
        check (
            provider in (
                'WEBHOOK_HTTP',
                'EMAIL_LOCAL_SINK',
                'EMAIL_SMTP'
            )
        ),

    destination text not null,
    destination_hash text not null,

    template_version text not null
        default 'accounting-export-ready-v1',

    idempotency_key text not null unique,

    status text not null default 'PENDING'
        check (
            status in (
                'PENDING',
                'DELIVERING',
                'RETRY_SCHEDULED',
                'SUCCEEDED',
                'FAILED'
            )
        ),

    payload jsonb
        not null default '{}'::jsonb,

    request_headers jsonb
        not null default '{}'::jsonb,

    attempt_count integer not null default 0
        check (attempt_count >= 0),

    max_attempts integer not null default 3
        check (max_attempts > 0),

    last_attempt_at timestamptz,
    next_attempt_at timestamptz,
    delivered_at timestamptz,

    last_error_code text,
    last_error_message text,

    created_by_user_id uuid not null
        references public.app_user_roles(user_id)
        on delete restrict,

    created_by_email text not null,
    created_by_role text not null,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.notification_delivery_attempts (
    id uuid primary key default gen_random_uuid(),

    notification_delivery_id uuid not null
        references public.notification_deliveries(id)
        on delete cascade,

    attempt_number integer not null
        check (attempt_number > 0),

    status text not null
        check (
            status in (
                'STARTED',
                'SUCCEEDED',
                'FAILED'
            )
        ),

    request_snapshot jsonb
        not null default '{}'::jsonb,

    response_status integer,
    response_headers jsonb
        not null default '{}'::jsonb,
    response_body_excerpt text,

    retryable boolean,
    retry_after_seconds integer
        check (
            retry_after_seconds is null
            or retry_after_seconds >= 0
        ),

    error_code text,
    error_message text,

    started_at timestamptz not null default now(),
    completed_at timestamptz,

    unique (
        notification_delivery_id,
        attempt_number
    )
);

create table if not exists public.notification_email_sink_messages (
    id uuid primary key default gen_random_uuid(),

    notification_delivery_id uuid not null unique
        references public.notification_deliveries(id)
        on delete cascade,

    recipient text not null,
    sender text not null,
    subject text not null,
    body_text text not null,
    body_html text,

    created_at timestamptz not null default now()
);

create table if not exists public.notification_test_webhook_receipts (
    id uuid primary key default gen_random_uuid(),

    token text not null,
    mode text not null
        check (
            mode in (
                'success',
                'fail-once'
            )
        ),

    request_headers jsonb
        not null default '{}'::jsonb,

    request_body jsonb
        not null default '{}'::jsonb,

    response_status integer not null,

    created_at timestamptz not null default now()
);

create index if not exists
    idx_notification_deliveries_export
    on public.notification_deliveries (
        accounting_export_id,
        created_at desc
    );

create index if not exists
    idx_notification_deliveries_due
    on public.notification_deliveries (
        status,
        next_attempt_at
    )
    where status in (
        'PENDING',
        'RETRY_SCHEDULED'
    );

create index if not exists
    idx_notification_delivery_attempts_delivery
    on public.notification_delivery_attempts (
        notification_delivery_id,
        attempt_number asc
    );

create index if not exists
    idx_notification_test_webhook_receipts_token
    on public.notification_test_webhook_receipts (
        token,
        created_at asc
    );

drop trigger if exists
    trg_notification_deliveries_set_updated_at
    on public.notification_deliveries;

create trigger trg_notification_deliveries_set_updated_at
before update on public.notification_deliveries
for each row
execute function public.set_updated_at();

alter table public.notification_deliveries
    enable row level security;

alter table public.notification_delivery_attempts
    enable row level security;

alter table public.notification_email_sink_messages
    enable row level security;

alter table public.notification_test_webhook_receipts
    enable row level security;

comment on table public.notification_deliveries is
    'Idempotent webhook and email delivery jobs for ready accounting exports.';

comment on table public.notification_delivery_attempts is
    'Immutable evidence for every notification delivery attempt.';

comment on table public.notification_email_sink_messages is
    'Local-development email provider output used by deterministic tests.';

comment on table public.notification_test_webhook_receipts is
    'Local webhook sink receipts for success and fail-once retry tests.';
