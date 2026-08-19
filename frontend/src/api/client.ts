import axios from "axios";
import type {
  AuthTokens,
  Customer,
  LeakageCase,
  LeakageInboxResponse,
  OrgMetrics,
  PaginatedResponse,
  Payment,
  Invoice,
  Contract,
  RecoveryDraft,
  SearchResponse,
  ImportJob,
  RevenueHealth,
  LeakageFilters,
} from "./types";

const API_BASE = "/api/v1";

// ─── Token management ───────────────────────────────────────────────────────

function getAccessToken(): string | null {
  return localStorage.getItem("access_token");
}

function getRefreshToken(): string | null {
  return localStorage.getItem("refresh_token");
}

function setTokens(tokens: AuthTokens) {
  localStorage.setItem("access_token", tokens.access_token);
  localStorage.setItem("refresh_token", tokens.refresh_token);
}

function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

// ─── Axios instance ─────────────────────────────────────────────────────────

const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

// Request interceptor — attach token
api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor — handle 401 with refresh
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const refresh = getRefreshToken();
      if (refresh) {
        try {
          const { data } = await axios.post(`${API_BASE}/auth/refresh`, {
            refresh_token: refresh,
          });
          setTokens(data);
          originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
          return api(originalRequest);
        } catch {
          clearTokens();
          window.location.href = "/login";
        }
      } else {
        clearTokens();
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// ─── Auth ───────────────────────────────────────────────────────────────────

export async function login(
  email: string,
  password: string
): Promise<AuthTokens> {
  const { data } = await axios.post(`${API_BASE}/auth/login`, {
    email,
    password,
  });
  setTokens(data);
  return data;
}

export async function register(
  org_name: string,
  email: string,
  password: string,
  name: string
): Promise<AuthTokens> {
  const { data } = await axios.post(`${API_BASE}/auth/register`, {
    organization_name: org_name,
    email,
    password,
    name,
  });
  setTokens(data);
  return data;
}

export function logout() {
  const refresh = getRefreshToken();
  if (refresh) {
    api.post("/auth/logout", { refresh_token: refresh }).catch(() => {});
  }
  clearTokens();
}

export function isAuthenticated(): boolean {
  return !!getAccessToken();
}

// ─── Customers ──────────────────────────────────────────────────────────────

export async function listCustomers(params: {
  page?: number;
  page_size?: number;
  search?: string;
}): Promise<PaginatedResponse<Customer>> {
  const { data } = await api.get("/customers", { params });
  return data;
}

export async function getCustomer(id: string): Promise<Customer> {
  const { data } = await api.get(`/customers/${id}`);
  return data;
}

export async function getRevenueHealth(
  id: string
): Promise<RevenueHealth> {
  const { data } = await api.get(`/customers/${id}/revenue-health`);
  return data;
}

// ─── Contracts ──────────────────────────────────────────────────────────────

export async function listContracts(params: {
  page?: number;
  page_size?: number;
  customer_id?: string;
}): Promise<PaginatedResponse<Contract>> {
  const { data } = await api.get("/contracts", { params });
  return data;
}

// ─── Invoices ───────────────────────────────────────────────────────────────

export async function listInvoices(params: {
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<Invoice>> {
  const { data } = await api.get("/invoices", { params });
  return data;
}

// ─── Payments ───────────────────────────────────────────────────────────────

export async function listPayments(params: {
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<Payment>> {
  const { data } = await api.get("/payments", { params });
  return data;
}

// ─── Leakage Inbox ──────────────────────────────────────────────────────────

export async function listLeakage(
  filters: LeakageFilters & { page?: number; page_size?: number }
): Promise<LeakageInboxResponse> {
  const { data } = await api.get("/leakage/inbox", { params: filters });
  return data;
}

export async function getLeakageCase(
  id: string
): Promise<LeakageCase> {
  const { data } = await api.get(`/leakage/${id}`);
  return data;
}

// ─── Approval actions ───────────────────────────────────────────────────────

export async function approveCase(
  id: string,
  notes?: string
): Promise<LeakageCase> {
  const { data } = await api.post(`/leakage/${id}/approve`, { notes });
  return data;
}

export async function rejectCase(
  id: string,
  reason: string
): Promise<LeakageCase> {
  const { data } = await api.post(`/leakage/${id}/reject`, { reason });
  return data;
}

export async function assignCase(
  id: string,
  user_id: string
): Promise<LeakageCase> {
  const { data } = await api.post(`/leakage/${id}/assign`, { user_id });
  return data;
}

export async function closeCase(id: string): Promise<LeakageCase> {
  const { data } = await api.post(`/leakage/${id}/close`);
  return data;
}

// ─── Recovery ───────────────────────────────────────────────────────────────

export async function createRecoveryDraft(
  caseId: string
): Promise<RecoveryDraft> {
  const { data } = await api.post(`/recovery/${caseId}/create`);
  return data;
}

export async function getRecoveryDrafts(
  caseId: string
): Promise<RecoveryDraft[]> {
  const { data } = await api.get(`/recovery/${caseId}`);
  return data;
}

export async function approveDraft(draftId: string): Promise<RecoveryDraft> {
  const { data } = await api.post(`/recovery/${draftId}/approve`);
  return data;
}

export async function executeDraft(draftId: string): Promise<RecoveryDraft> {
  const { data } = await api.post(`/recovery/${draftId}/execute`);
  return data;
}

// ─── Metrics ────────────────────────────────────────────────────────────────

export async function getOrgMetrics(): Promise<OrgMetrics> {
  const { data } = await api.get("/verification/org/current/metrics");
  return data;
}

// ─── Search ─────────────────────────────────────────────────────────────────

export async function search(
  q: string,
  entity_type?: string
): Promise<SearchResponse> {
  const { data } = await api.get("/search", {
    params: { q, entity_type },
  });
  return data;
}

// ─── Imports ────────────────────────────────────────────────────────────────

export async function uploadImport(
  file: File,
  targetEntity: string
): Promise<ImportJob> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("target_entity", targetEntity);
  const { data } = await api.post("/imports", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getImportJob(id: string): Promise<ImportJob> {
  const { data } = await api.get(`/imports/${id}`);
  return data;
}

export async function getImportErrors(
  id: string,
  params?: { page?: number; page_size?: number }
): Promise<{ items: ImportJob["errors"]; total: number }> {
  const { data } = await api.get(`/imports/${id}/errors`, { params });
  return data;
}

export { api };
