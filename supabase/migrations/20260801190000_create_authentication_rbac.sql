create table if not exists public.app_user_roles (
    id uuid primary key default gen_random_uuid(),

    user_id uuid not null unique,

    email text not null unique,
    display_name text not null,

    role text not null
        check (
            role in (
                'AP_CLERK',
                'REVIEWER',
                'ADMIN'
            )
        ),

    active boolean not null default true,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.security_audit_events (
    id uuid primary key default gen_random_uuid(),

    request_id uuid not null,

    user_id uuid,
    email text,
    app_role text,

    event_type text not null
        check (
            event_type in (
                'AUTHENTICATION_SUCCEEDED',
                'AUTHENTICATION_FAILED',
                'AUTHORIZATION_DENIED'
            )
        ),

    method text not null,
    path text not null,

    status_code integer not null,

    reason text not null,

    metadata jsonb
        not null default '{}'::jsonb,

    created_at timestamptz not null default now()
);

create index if not exists
    idx_app_user_roles_user_id
    on public.app_user_roles (
        user_id
    );

create index if not exists
    idx_app_user_roles_role
    on public.app_user_roles (
        role,
        active
    );

create index if not exists
    idx_security_audit_events_created
    on public.security_audit_events (
        created_at desc
    );

create index if not exists
    idx_security_audit_events_user
    on public.security_audit_events (
        user_id,
        created_at desc
    );

create index if not exists
    idx_security_audit_events_type
    on public.security_audit_events (
        event_type,
        created_at desc
    );

alter table public.app_user_roles
    enable row level security;

alter table public.security_audit_events
    enable row level security;

comment on table public.app_user_roles is
    'Application authorization roles mapped to Supabase JWT subject identifiers.';

comment on table public.security_audit_events is
    'Authentication and authorization audit trail for protected API requests.';