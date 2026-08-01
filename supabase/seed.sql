-- Synthetic DocuFlow seed data will be added in a later milestone.
-- DOCUFLOW_VENDOR_PO_MATCHING_SEED

insert into public.vendors (
    id,
    vendor_code,
    canonical_name,
    normalized_name,
    tax_identifier,
    status
)
values (
    '10000000-0000-0000-0000-000000000001',
    'MERIDIAN-001',
    'Meridian Office Supplies',
    'MERIDIAN OFFICE SUPPLIES',
    'TAX-MERIDIAN-001',
    'ACTIVE'
)
on conflict (vendor_code)
do update set
    canonical_name = excluded.canonical_name,
    normalized_name = excluded.normalized_name,
    tax_identifier = excluded.tax_identifier,
    status = excluded.status;

insert into public.vendor_aliases (
    id,
    vendor_id,
    alias_name,
    normalized_alias,
    active
)
values (
    '10000000-0000-0000-0000-000000000101',
    '10000000-0000-0000-0000-000000000001',
    'Meridian Office Supply',
    'MERIDIAN OFFICE SUPPLY',
    true
)
on conflict (
    vendor_id,
    normalized_alias
)
do update set
    alias_name = excluded.alias_name,
    active = excluded.active;

insert into public.purchase_orders (
    id,
    po_number,
    vendor_id,
    currency,
    status,
    subtotal,
    tax_amount,
    total_amount
)
values (
    '20000000-0000-0000-0000-000000000001',
    'PO-7001',
    '10000000-0000-0000-0000-000000000001',
    'USD',
    'OPEN',
    120.00,
    18.00,
    138.00
)
on conflict (po_number)
do update set
    vendor_id = excluded.vendor_id,
    currency = excluded.currency,
    status = excluded.status,
    subtotal = excluded.subtotal,
    tax_amount = excluded.tax_amount,
    total_amount = excluded.total_amount;

insert into public.purchase_order_lines (
    id,
    purchase_order_id,
    line_number,
    description,
    normalized_description,
    quantity,
    unit_price,
    line_total
)
values
(
    '30000000-0000-0000-0000-000000000001',
    '20000000-0000-0000-0000-000000000001',
    1,
    'Printer Paper',
    'PRINTER PAPER',
    2,
    50.00,
    100.00
),
(
    '30000000-0000-0000-0000-000000000002',
    '20000000-0000-0000-0000-000000000001',
    2,
    'Blue Pens',
    'BLUE PENS',
    1,
    20.00,
    20.00
)
on conflict (
    purchase_order_id,
    line_number
)
do update set
    description = excluded.description,
    normalized_description =
        excluded.normalized_description,
    quantity = excluded.quantity,
    unit_price = excluded.unit_price,
    line_total = excluded.line_total;
-- DOCUFLOW_AUTHENTICATION_RBAC_SEED

insert into public.app_user_roles (
    id,
    user_id,
    email,
    display_name,
    role,
    active
)
values
(
    '91000000-0000-0000-0000-000000000001',
    '90000000-0000-0000-0000-000000000001',
    'clerk@docuflow.local',
    'Local AP Clerk',
    'AP_CLERK',
    true
),
(
    '91000000-0000-0000-0000-000000000002',
    '90000000-0000-0000-0000-000000000002',
    'reviewer@docuflow.local',
    'Local AP Reviewer',
    'REVIEWER',
    true
),
(
    '91000000-0000-0000-0000-000000000003',
    '90000000-0000-0000-0000-000000000003',
    'admin@docuflow.local',
    'Local Administrator',
    'ADMIN',
    true
)
on conflict (user_id)
do update set
    email = excluded.email,
    display_name = excluded.display_name,
    role = excluded.role,
    active = excluded.active,
    updated_at = now();
