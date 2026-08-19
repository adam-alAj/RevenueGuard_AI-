// ─── Auth ───────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  organization_id: string;
  is_active: boolean;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// ─── Leakage ────────────────────────────────────────────────────────────────

export type LeakageType =
  | "missing_invoice"
  | "underbilling"
  | "pricing_mismatch"
  | "overdue_invoice"
  | "partial_payment"
  | "contract_expiration"
  | "subscription_renewal"
  | "late_billing"
  | "uncollected_invoice"
  | "other";

export type Severity = "critical" | "high" | "medium" | "low";

export type CaseStatus =
  | "detected"
  | "investigating"
  | "pending_review"
  | "approved"
  | "rejected"
  | "action_pending"
  | "action_completed"
  | "verified"
  | "recovered"
  | "false_positive"
  | "legitimate_exception"
  | "closed";

export interface LeakageCase {
  case_id: string;
  case_number: string;
  leakage_type: LeakageType;
  status: CaseStatus;
  severity: Severity | null;
  customer_id: string | null;
  customer_name?: string;
  potential_leakage: string | null;
  confidence: string | null;
  assigned_to: string | null;
  created_at: string | null;
  description?: string;
  organization_id: string;
}

export interface LeakageInboxResponse {
  items: LeakageCase[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  filters_applied: Record<string, unknown>;
}

// ─── Customer ───────────────────────────────────────────────────────────────

export interface Customer {
  id: string;
  organization_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  company: string | null;
  external_id: string | null;
  is_active: boolean;
  created_at?: string;
}

export interface RevenueHealth {
  customer_id: string;
  customer_name: string;
  total_contract_value: string;
  total_invoiced: string;
  total_paid: string;
  total_outstanding: string;
  potential_leakage: string;
  recovery_history: string;
  active_subscriptions: number;
  billing_anomalies: number;
}

// ─── Contract ───────────────────────────────────────────────────────────────

export interface Contract {
  id: string;
  name: string;
  customer_id: string;
  organization_id: string;
  external_id: string | null;
  currency: string;
  start_date: string;
  expiration_date: string;
  status: string;
  created_at: string;
}

// ─── Invoice ────────────────────────────────────────────────────────────────

export interface Invoice {
  id: string;
  invoice_number: string;
  customer_id: string;
  contract_id: string | null;
  organization_id: string;
  total: string;
  status: string;
  created_at: string;
}

// ─── Payment ────────────────────────────────────────────────────────────────

export interface Payment {
  id: string;
  payment_number: string;
  customer_id: string;
  invoice_id: string | null;
  organization_id: string;
  amount: string;
  status: string;
  created_at: string;
}

// ─── Recovery ───────────────────────────────────────────────────────────────

export type RecoveryActionType =
  | "create_invoice_draft"
  | "send_payment_reminder"
  | "request_internal_investigation"
  | "correct_pricing"
  | "contact_account_manager"
  | "renew_contract"
  | "reconcile_payment"
  | "issue_correction"
  | "escalate_to_finance_manager";

export type DraftStatus = "draft" | "ready_for_manual_action" | "action_completed";

export interface RecoveryDraft {
  draft_id: string;
  case_id: string;
  action_type: RecoveryActionType;
  status: DraftStatus;
  draft_content: Record<string, unknown>;
  created_at: string;
}

// ─── Import ─────────────────────────────────────────────────────────────────

export interface ImportJob {
  id: string;
  target_entity: string;
  status: string;
  records_processed: number;
  records_imported: number;
  records_rejected: number;
  created_at: string;
  errors?: ImportError[];
}

export interface ImportError {
  row_number: number;
  reason: string;
  raw_data: Record<string, unknown>;
}

// ─── Search ─────────────────────────────────────────────────────────────────

export interface SearchResult {
  entity_type: "customer" | "contract" | "invoice" | "case";
  entity_id: string;
  title: string;
  subtitle: string | null;
  matched_field: string;
  relevance_score: number;
}

export interface SearchResponse {
  items: SearchResult[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  query: string;
}

// ─── Metrics ────────────────────────────────────────────────────────────────

export interface OrgMetrics {
  total_potential_leakage: string;
  total_confirmed_leakage: string;
  total_recovered_revenue: string;
  recovery_rate: number;
  open_cases: number;
  critical_cases: number;
}

// ─── Pagination ─────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ─── Leakage Filters ────────────────────────────────────────────────────────

export interface LeakageFilters {
  leakage_type?: string;
  status?: string;
  severity?: string;
  customer_id?: string;
  min_amount?: number;
  max_amount?: number;
  min_confidence?: number;
  max_confidence?: number;
  date_from?: string;
  date_to?: string;
  assigned_to?: string;
  search?: string;
}
