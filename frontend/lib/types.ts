export type AppRole =
  | "AP_CLERK"
  | "REVIEWER"
  | "ADMIN";

export type AuthenticatedProfile = {
  authenticated: true;
  user: {
    user_id: string;
    email: string;
    display_name: string;
    role: AppRole;
    token_role: string;
    token_expires_at: number;
  };
};

export type DashboardMetrics = {
  total_documents: number;
  auto_approved: number;
  review_required: number;
  rejected: number;
  failed: number;
  open_reviews: number;
  claimed_reviews: number;
  ready_exports: number;
  notifications_in_flight: number;
  notification_failures: number;
  approval_rate: number;
};

export type DashboardDocument = {
  id: string;
  original_filename: string;
  status: string;
  source_channel: string;
  created_at: string;
  updated_at: string;
  validation_outcome: string | null;
  blocking_validation_count?: number;
  duplicate_outcome: string | null;
  business_duplicate_blocking?: boolean;
  vendor_match_outcome: string | null;
  po_match_outcome: string | null;
  matching_blocking?: boolean;
  decision_outcome: string | null;
  decision_reason_codes?: string[];
  latest_review_case_id?: string | null;
  final_resolution_source: string | null;
  vendor_name: string | null;
  invoice_number: string | null;
  invoice_date?: string | null;
  due_date?: string | null;
  purchase_order_number?: string | null;
  currency: string | null;
  total_amount: string | null;
};

export type DashboardOverview = {
  requested_by: {
    user_id: string;
    email: string;
    display_name: string;
    role: AppRole;
  };
  metrics: DashboardMetrics;
  recent_documents: DashboardDocument[];
};

export type DocumentListResponse = {
  requested_by: {
    user_id: string;
    email: string;
    display_name: string;
    role: AppRole;
  };
  filters: {
    status: string | null;
    search: string | null;
    sort_by: string;
    sort_direction: "asc" | "desc";
  };
  pagination: {
    limit: number;
    offset: number;
    total: number;
  };
  documents: DashboardDocument[];
};

export type ReviewQueueItem = {
  id: string;
  document_id: string;
  status: string;
  priority: string;
  reason_codes: string[];
  explanation: string;
  claimed_by_user_id: string | null;
  claimed_by_email: string | null;
  claimed_at: string | null;
  resolved_by_user_id: string | null;
  resolved_by_email: string | null;
  resolved_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  original_filename: string;
  document_status: string;
  vendor_name: string | null;
  invoice_number: string | null;
  currency: string | null;
  total_amount: string | null;
};

export type ReviewListResponse = {
  requested_by: {
    user_id: string;
    email: string;
    display_name: string;
    role: AppRole;
  };
  filters: {
    status: string | null;
    search: string | null;
    owner: "ALL" | "UNCLAIMED" | "MINE" | "CLAIMED";
    sort_by: string;
    sort_direction: "asc" | "desc";
  };
  pagination: {
    limit: number;
    offset: number;
    total: number;
  };
  reviews: ReviewQueueItem[];
};

export type LineItem = {
  id: string;
  line_number: number;
  description: string;
  supplier_sku: string | null;
  quantity: string | null;
  unit_of_measure: string | null;
  unit_price: string | null;
  tax_rate: string | null;
  line_total: string | null;
  currency: string | null;
  confidence: string;
};

export type AccountingExport = {
  id: string;
  export_format: string;
  schema_version: string;
  source_kind: string;
  source_version: string;
  status: string;
  file_name: string | null;
  content_type: string | null;
  payload_sha256: string | null;
  row_count: number | null;
  requested_at: string;
  completed_at: string | null;
};

export type NotificationDelivery = {
  id: string;
  accounting_export_id: string;
  channel: string;
  provider: string;
  destination: string;
  status: string;
  attempt_count: number;
  max_attempts: number;
  last_attempt_at: string | null;
  next_attempt_at: string | null;
  delivered_at: string | null;
  last_error_code: string | null;
  last_error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type DocumentDetailResponse = {
  requested_by: {
    user_id: string;
    email: string;
    display_name: string;
    role: AppRole;
  };
  document: DashboardDocument & {
    id: string;
    status: string;
    original_filename: string;
    subtotal: string | null;
    discount_amount: string | null;
    shipping_amount: string | null;
    tax_amount: string | null;
    total_amount: string | null;
    decision_reason_codes: string[];
    decision_explanation: string | null;
  };
  line_items: LineItem[];
  decision: {
    id: string;
    status: string;
    outcome: string | null;
    blocking: boolean;
    reason_codes: string[];
    explanation: string | null;
    policy_version: string;
    started_at: string;
    completed_at: string | null;
  } | null;
  review_case: {
    id: string;
    status: string;
    priority: string;
    reason_codes: string[];
    explanation: string;
    claimed_by_user_id: string | null;
    claimed_by_email: string | null;
    claimed_at: string | null;
    resolved_by_user_id: string | null;
    resolved_by_email: string | null;
    resolved_at: string | null;
    resolution_note: string | null;
    version: number;
    latest_control_run_id?: string | null;
    created_at?: string;
    updated_at?: string;
  } | null;
  exports: AccountingExport[];
  notifications: NotificationDelivery[];
};

export type ReviewCaseRecord = {
  id: string;
  document_id: string;
  decision_run_id: string;
  status: string;
  priority: string;
  reason_codes: string[];
  explanation: string;
  claimed_by_user_id: string | null;
  claimed_by_email: string | null;
  claimed_at: string | null;
  resolved_by_user_id: string | null;
  resolved_by_email: string | null;
  resolved_at: string | null;
  resolution_note: string | null;
  version: number;
  latest_control_run_id: string | null;
  created_at: string;
  updated_at: string;
  filename: string;
  source_channel: string;
  document_status: string;
  decision_outcome: string | null;
  decision_reason_codes: string[];
  decision_explanation: string | null;
  decided_at: string | null;
};

export type ReviewEvent = {
  id: string;
  actor_type: string;
  actor_user_id: string | null;
  actor_email: string | null;
  actor_role: string | null;
  event_type: string;
  message: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type ReviewCorrection = {
  id: string;
  review_case_id: string;
  document_id: string;
  target_type: "HEADER" | "LINE_ITEM";
  line_item_id: string | null;
  field_name: string;
  original_value: unknown;
  corrected_value: unknown;
  reason: string;
  status: string;
  proposed_by_user_id: string;
  proposed_by_email: string;
  proposed_by_role: string;
  proposed_at: string;
  applied_by_user_id: string | null;
  applied_by_email: string | null;
  applied_at: string | null;
  rejected_by_user_id: string | null;
  rejected_by_email: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
};

export type ReviewControlRun = {
  id: string;
  review_case_id: string;
  document_id: string;
  case_version: number;
  policy_version: string;
  status: string;
  outcome: string | null;
  validation_passed: boolean | null;
  duplicate_outcome: string | null;
  vendor_outcome: string | null;
  po_outcome: string | null;
  blocking_reasons: string[];
  error_code: string | null;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
};

export type ReviewSnapshot = {
  review_case: ReviewCaseRecord;
  events: ReviewEvent[];
  corrections: ReviewCorrection[];
  latest_control_run: ReviewControlRun | null;
  requested_by: {
    user_id: string;
    role: AppRole;
  };
};

export type EffectiveInvoiceHeader = {
  id: string;
  document_id: string;
  invoice_extraction_id: string;
  vendor_name: string | null;
  invoice_number: string | null;
  invoice_date: string | null;
  due_date: string | null;
  purchase_order_number: string | null;
  currency: string | null;
  subtotal: string | null;
  discount_amount: string | null;
  shipping_amount: string | null;
  tax_amount: string | null;
  total_amount: string | null;
};

export type EffectiveInvoiceLine = {
  id: string;
  line_number: number;
  description: string | null;
  supplier_sku: string | null;
  quantity: string | null;
  unit_of_measure: string | null;
  unit_price: string | null;
  tax_rate: string | null;
  line_total: string | null;
  currency: string | null;
};

export type EffectiveInvoiceSnapshot = {
  review_case: ReviewCaseRecord;
  original: {
    header: EffectiveInvoiceHeader;
    lines: EffectiveInvoiceLine[];
  };
  effective: {
    header: EffectiveInvoiceHeader;
    lines: EffectiveInvoiceLine[];
  };
  applied_corrections: ReviewCorrection[];
  requested_by: {
    user_id: string;
    role: AppRole;
  };
};
