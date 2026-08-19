import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as client from "../client";
import type { LeakageFilters } from "../types";

// ─── Customers ──────────────────────────────────────────────────────────────

export function useCustomers(params: {
  page?: number;
  page_size?: number;
  search?: string;
}) {
  return useQuery({
    queryKey: ["customers", params],
    queryFn: () => client.listCustomers(params),
  });
}

export function useCustomer(id: string) {
  return useQuery({
    queryKey: ["customer", id],
    queryFn: () => client.getCustomer(id),
    enabled: !!id,
  });
}

export function useRevenueHealth(id: string) {
  return useQuery({
    queryKey: ["revenueHealth", id],
    queryFn: () => client.getRevenueHealth(id),
    enabled: !!id,
  });
}

// ─── Contracts ──────────────────────────────────────────────────────────────

export function useContracts(params: {
  page?: number;
  page_size?: number;
  customer_id?: string;
}) {
  return useQuery({
    queryKey: ["contracts", params],
    queryFn: () => client.listContracts(params),
  });
}

// ─── Invoices ───────────────────────────────────────────────────────────────

export function useInvoices(params: { page?: number; page_size?: number }) {
  return useQuery({
    queryKey: ["invoices", params],
    queryFn: () => client.listInvoices(params),
  });
}

// ─── Payments ───────────────────────────────────────────────────────────────

export function usePayments(params: { page?: number; page_size?: number }) {
  return useQuery({
    queryKey: ["payments", params],
    queryFn: () => client.listPayments(params),
  });
}

// ─── Leakage Inbox ──────────────────────────────────────────────────────────

export function useLeakageInbox(
  filters: LeakageFilters & { page?: number; page_size?: number }
) {
  return useQuery({
    queryKey: ["leakageInbox", filters],
    queryFn: () => client.listLeakage(filters),
  });
}

export function useLeakageCase(id: string) {
  return useQuery({
    queryKey: ["leakageCase", id],
    queryFn: () => client.getLeakageCase(id),
    enabled: !!id,
  });
}

// ─── Approval mutations ─────────────────────────────────────────────────────

export function useApproveCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) =>
      client.approveCase(id, notes),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["leakageCase", variables.id] });
      qc.invalidateQueries({ queryKey: ["leakageInbox"] });
    },
  });
}

export function useRejectCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      client.rejectCase(id, reason),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["leakageCase", variables.id] });
      qc.invalidateQueries({ queryKey: ["leakageInbox"] });
    },
  });
}

export function useAssignCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, user_id }: { id: string; user_id: string }) =>
      client.assignCase(id, user_id),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["leakageCase", variables.id] });
    },
  });
}

export function useCloseCase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => client.closeCase(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: ["leakageCase", id] });
      qc.invalidateQueries({ queryKey: ["leakageInbox"] });
    },
  });
}

// ─── Recovery ───────────────────────────────────────────────────────────────

export function useRecoveryDrafts(caseId: string) {
  return useQuery({
    queryKey: ["recoveryDrafts", caseId],
    queryFn: () => client.getRecoveryDrafts(caseId),
    enabled: !!caseId,
  });
}

export function useCreateRecoveryDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (caseId: string) => client.createRecoveryDraft(caseId),
    onSuccess: (_data, caseId) => {
      qc.invalidateQueries({ queryKey: ["recoveryDrafts", caseId] });
    },
  });
}

export function useApproveDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (draftId: string) => client.approveDraft(draftId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["recoveryDrafts"] });
    },
  });
}

export function useExecuteDraft() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (draftId: string) => client.executeDraft(draftId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["recoveryDrafts"] });
      qc.invalidateQueries({ queryKey: ["leakageInbox"] });
    },
  });
}

// ─── Metrics ────────────────────────────────────────────────────────────────

export function useOrgMetrics() {
  return useQuery({
    queryKey: ["orgMetrics"],
    queryFn: () => client.getOrgMetrics(),
    refetchInterval: 30000, // refresh every 30s
  });
}

// ─── Search ─────────────────────────────────────────────────────────────────

export function useSearch(q: string, entity_type?: string) {
  return useQuery({
    queryKey: ["search", q, entity_type],
    queryFn: () => client.search(q, entity_type),
    enabled: q.length >= 2,
  });
}

// ─── Imports ────────────────────────────────────────────────────────────────

export function useUploadImport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      file,
      targetEntity,
    }: {
      file: File;
      targetEntity: string;
    }) => client.uploadImport(file, targetEntity),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["imports"] });
    },
  });
}

export function useImportJob(id: string) {
  return useQuery({
    queryKey: ["importJob", id],
    queryFn: () => client.getImportJob(id),
    enabled: !!id,
  });
}
