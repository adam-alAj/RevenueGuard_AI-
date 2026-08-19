import { Link } from "react-router-dom";
import {
  DollarSign,
  TrendingUp,
  CheckCircle2,
  Clock,
} from "lucide-react";
import { useLeakageInbox, useOrgMetrics } from "../api/hooks/useQueries";
import { formatCurrency, formatPercent } from "../lib/utils";
import type { CaseStatus } from "../api/types";

const pipelineStages: {
  label: string;
  statuses: CaseStatus[];
  color: string;
  bgColor: string;
}[] = [
  {
    label: "Detected",
    statuses: ["detected"],
    color: "bg-blue-500",
    bgColor: "bg-blue-50",
  },
  {
    label: "Investigating",
    statuses: ["investigating"],
    color: "bg-purple-500",
    bgColor: "bg-purple-50",
  },
  {
    label: "Pending Review",
    statuses: ["pending_review"],
    color: "bg-amber-500",
    bgColor: "bg-amber-50",
  },
  {
    label: "Approved",
    statuses: ["approved"],
    color: "bg-green-500",
    bgColor: "bg-green-50",
  },
  {
    label: "In Progress",
    statuses: ["action_pending", "action_completed", "verified"],
    color: "bg-cyan-500",
    bgColor: "bg-cyan-50",
  },
  {
    label: "Recovered",
    statuses: ["recovered"],
    color: "bg-emerald-600",
    bgColor: "bg-emerald-50",
  },
  {
    label: "Closed/Rejected",
    statuses: [
      "closed",
      "rejected",
      "false_positive",
      "legitimate_exception",
    ],
    color: "bg-gray-400",
    bgColor: "bg-gray-50",
  },
];

export function RecoveryCenter() {
  const { data: metrics } = useOrgMetrics();
  const { data: allCases } = useLeakageInbox({ page_size: 200 });

  // Count cases per pipeline stage
  const stageCounts = pipelineStages.map((stage) => ({
    ...stage,
    count:
      allCases?.items.filter((c) => stage.statuses.includes(c.status))
        .length || 0,
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Recovery Center</h1>
        <p className="mt-1 text-sm text-gray-500">
          Track recovery progress across all detected leakage cases
        </p>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-red-500 p-2">
              <DollarSign className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Potential Leakage</p>
              <p className="text-xl font-bold text-gray-900">
                {formatCurrency(metrics?.total_potential_leakage)}
              </p>
            </div>
          </div>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-green-500 p-2">
              <CheckCircle2 className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Recovered</p>
              <p className="text-xl font-bold text-gray-900">
                {formatCurrency(metrics?.total_recovered_revenue)}
              </p>
            </div>
          </div>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-blue-500 p-2">
              <TrendingUp className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Recovery Rate</p>
              <p className="text-xl font-bold text-gray-900">
                {formatPercent(metrics?.recovery_rate)}
              </p>
            </div>
          </div>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-amber-500 p-2">
              <Clock className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Open Cases</p>
              <p className="text-xl font-bold text-gray-900">
                {metrics?.open_cases ?? 0}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Pipeline */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          Recovery Pipeline
        </h2>
        <div className="grid grid-cols-7 gap-3">
          {stageCounts.map((stage) => (
            <div key={stage.label} className={`${stage.bgColor} rounded-lg p-4 text-center`}>
              <div className={`mx-auto mb-2 h-2 w-full rounded-full ${stage.color}`} />
              <p className="text-2xl font-bold text-gray-900">{stage.count}</p>
              <p className="mt-1 text-xs font-medium text-gray-600">
                {stage.label}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Recent cases */}
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Active Recovery Cases
          </h2>
        </div>
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500">
                Case
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500">
                Customer
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500">
                Type
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500">
                Amount
              </th>
              <th className="px-6 py-3 text-center text-xs font-medium text-gray-500">
                Status
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {allCases?.items
              .filter((c) => !["closed", "recovered"].includes(c.status))
              .slice(0, 20)
              .map((c) => (
                <tr key={c.case_id} className="hover:bg-gray-50">
                  <td className="px-6 py-3">
                    <Link
                      to={`/case/${c.case_id}`}
                      className="text-sm font-medium text-blue-600 hover:text-blue-700"
                    >
                      {c.case_number}
                    </Link>
                  </td>
                  <td className="px-6 py-3 text-sm text-gray-700">
                    {c.customer_name || c.customer_id || "—"}
                  </td>
                  <td className="px-6 py-3 text-sm text-gray-700">
                    {c.leakage_type.replace(/_/g, " ")}
                  </td>
                  <td className="px-6 py-3 text-right text-sm font-medium text-gray-900">
                    {formatCurrency(c.potential_leakage)}
                  </td>
                  <td className="px-6 py-3 text-center">
                    <span
                      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${
                        c.status === "approved"
                          ? "border-green-200 bg-green-100 text-green-800"
                          : c.status === "rejected"
                            ? "border-red-200 bg-red-100 text-red-800"
                            : "border-gray-200 bg-gray-100 text-gray-800"
                      }`}
                    >
                      {c.status.replace(/_/g, " ")}
                    </span>
                  </td>
                </tr>
              ))}
            {(!allCases?.items ||
              allCases.items.filter((c) => !["closed", "recovered"].includes(c.status))
                .length === 0) && (
              <tr>
                <td
                  colSpan={5}
                  className="px-6 py-12 text-center text-sm text-gray-500"
                >
                  No active recovery cases
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
