import { useState } from "react";
import { Link } from "react-router-dom";
import { Filter, X, ChevronLeft, ChevronRight } from "lucide-react";
import { useLeakageInbox } from "../api/hooks/useQueries";
import { SeverityBadge, StatusBadge } from "../components/StatusBadge";
import {
  formatCurrency,
  formatPercent,
  daysSince,
  leakageTypeLabel,
} from "../lib/utils";
import type { LeakageFilters } from "../api/types";

const leakageTypes = [
  "missing_invoice",
  "underbilling",
  "pricing_mismatch",
  "overdue_invoice",
  "partial_payment",
  "contract_expiration",
  "subscription_renewal",
  "late_billing",
  "uncollected_invoice",
  "other",
];

const statuses = [
  "detected",
  "investigating",
  "pending_review",
  "approved",
  "rejected",
  "action_pending",
  "action_completed",
  "verified",
  "recovered",
  "false_positive",
  "legitimate_exception",
  "closed",
];

const severities = ["critical", "high", "medium", "low"];

function FilterPanel({
  filters,
  onChange,
}: {
  filters: LeakageFilters;
  onChange: (f: LeakageFilters) => void;
}) {
  const [showFilters, setShowFilters] = useState(false);
  const activeCount = Object.values(filters).filter(Boolean).length;

  return (
    <div>
      <button
        onClick={() => setShowFilters(!showFilters)}
        className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
      >
        <Filter className="h-4 w-4" />
        Filters
        {activeCount > 0 && (
          <span className="rounded-full bg-blue-100 px-1.5 py-0.5 text-xs font-medium text-blue-700">
            {activeCount}
          </span>
        )}
      </button>

      {showFilters && (
        <div className="mt-3 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {/* Leakage Type */}
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">
                Leakage Type
              </label>
              <select
                value={filters.leakage_type || ""}
                onChange={(e) =>
                  onChange({
                    ...filters,
                    leakage_type: e.target.value || undefined,
                  })
                }
                className="w-full rounded-lg border border-gray-200 px-2 py-1.5 text-sm"
              >
                <option value="">All types</option>
                {leakageTypes.map((t) => (
                  <option key={t} value={t}>
                    {leakageTypeLabel(t)}
                  </option>
                ))}
              </select>
            </div>

            {/* Status */}
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">
                Status
              </label>
              <select
                value={filters.status || ""}
                onChange={(e) =>
                  onChange({ ...filters, status: e.target.value || undefined })
                }
                className="w-full rounded-lg border border-gray-200 px-2 py-1.5 text-sm"
              >
                <option value="">All statuses</option>
                {statuses.map((s) => (
                  <option key={s} value={s}>
                    {s.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </div>

            {/* Severity */}
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">
                Severity
              </label>
              <select
                value={filters.severity || ""}
                onChange={(e) =>
                  onChange({
                    ...filters,
                    severity: e.target.value || undefined,
                  })
                }
                className="w-full rounded-lg border border-gray-200 px-2 py-1.5 text-sm"
              >
                <option value="">All severities</option>
                {severities.map((s) => (
                  <option key={s} value={s}>
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </option>
                ))}
              </select>
            </div>

            {/* Amount range */}
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">
                Min Amount ($)
              </label>
              <input
                type="number"
                value={filters.min_amount || ""}
                onChange={(e) =>
                  onChange({
                    ...filters,
                    min_amount: e.target.value
                      ? Number(e.target.value)
                      : undefined,
                  })
                }
                placeholder="0"
                className="w-full rounded-lg border border-gray-200 px-2 py-1.5 text-sm"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">
                Max Amount ($)
              </label>
              <input
                type="number"
                value={filters.max_amount || ""}
                onChange={(e) =>
                  onChange({
                    ...filters,
                    max_amount: e.target.value
                      ? Number(e.target.value)
                      : undefined,
                  })
                }
                placeholder="No limit"
                className="w-full rounded-lg border border-gray-200 px-2 py-1.5 text-sm"
              />
            </div>

            {/* Confidence range */}
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-500">
                Min Confidence
              </label>
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={filters.min_confidence || ""}
                onChange={(e) =>
                  onChange({
                    ...filters,
                    min_confidence: e.target.value
                      ? Number(e.target.value)
                      : undefined,
                  })
                }
                placeholder="0"
                className="w-full rounded-lg border border-gray-200 px-2 py-1.5 text-sm"
              />
            </div>

            {/* Search */}
            <div className="col-span-2">
              <label className="mb-1 block text-xs font-medium text-gray-500">
                Search
              </label>
              <input
                type="text"
                value={filters.search || ""}
                onChange={(e) =>
                  onChange({
                    ...filters,
                    search: e.target.value || undefined,
                  })
                }
                placeholder="Search case number or description..."
                className="w-full rounded-lg border border-gray-200 px-2 py-1.5 text-sm"
              />
            </div>
          </div>

          {/* Clear filters */}
          {activeCount > 0 && (
            <button
              onClick={() => onChange({})}
              className="mt-3 flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700"
            >
              <X className="h-3 w-3" />
              Clear all filters
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function LeakageInbox() {
  const [filters, setFilters] = useState<LeakageFilters>({});
  const [page, setPage] = useState(1);
  const { data, isLoading } = useLeakageInbox({ ...filters, page, page_size: 20 });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Leakage Inbox</h1>
          <p className="mt-1 text-sm text-gray-500">
            {data?.total ?? 0} cases detected
          </p>
        </div>
      </div>

      <FilterPanel filters={filters} onChange={setFilters} />

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">
                Case
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">
                Customer
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">
                Type
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">
                Amount
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">
                Confidence
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium text-gray-500">
                Severity
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">
                Age
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium text-gray-500">
                Status
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">
                Owner
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading ? (
              <tr>
                <td
                  colSpan={9}
                  className="px-4 py-12 text-center text-sm text-gray-500"
                >
                  Loading...
                </td>
              </tr>
            ) : data?.items.length === 0 ? (
              <tr>
                <td
                  colSpan={9}
                  className="px-4 py-12 text-center text-sm text-gray-500"
                >
                  No cases found matching your filters
                </td>
              </tr>
            ) : (
              data?.items.map((item) => (
                <tr
                  key={item.case_id}
                  className="hover:bg-gray-50"
                >
                  <td className="px-4 py-3">
                    <Link
                      to={`/case/${item.case_id}`}
                      className="text-sm font-medium text-blue-600 hover:text-blue-700"
                    >
                      {item.case_number}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {item.customer_name || item.customer_id || "—"}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {leakageTypeLabel(item.leakage_type)}
                  </td>
                  <td className="px-4 py-3 text-right text-sm font-medium text-gray-900">
                    {formatCurrency(item.potential_leakage)}
                  </td>
                  <td className="px-4 py-3 text-right text-sm text-gray-700">
                    {formatPercent(
                      item.confidence ? parseFloat(item.confidence) : null
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <SeverityBadge severity={item.severity} />
                  </td>
                  <td className="px-4 py-3 text-right text-sm text-gray-500">
                    {daysSince(item.created_at)}d
                  </td>
                  <td className="px-4 py-3 text-center">
                    <StatusBadge status={item.status} />
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {item.assigned_to
                      ? item.assigned_to.split("-").pop()
                      : "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Pagination */}
        {data && data.total_pages > 1 && (
          <div className="flex items-center justify-between border-t border-gray-200 bg-gray-50 px-4 py-3">
            <div className="text-sm text-gray-500">
              Page {data.page} of {data.total_pages}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page <= 1}
                className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                onClick={() =>
                  setPage(Math.min(data.total_pages, page + 1))
                }
                disabled={page >= data.total_pages}
                className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
