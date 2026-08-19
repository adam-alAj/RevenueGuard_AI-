import type { CaseStatus, Severity } from "../api/types";

const severityColors: Record<string, string> = {
  critical: "bg-red-100 text-red-800 border-red-200",
  high: "bg-orange-100 text-orange-800 border-orange-200",
  medium: "bg-yellow-100 text-yellow-800 border-yellow-200",
  low: "bg-green-100 text-green-800 border-green-200",
};

const statusColors: Record<string, string> = {
  detected: "bg-blue-100 text-blue-800 border-blue-200",
  investigating: "bg-purple-100 text-purple-800 border-purple-200",
  pending_review: "bg-amber-100 text-amber-800 border-amber-200",
  approved: "bg-green-100 text-green-800 border-green-200",
  rejected: "bg-red-100 text-red-800 border-red-200",
  action_pending: "bg-cyan-100 text-cyan-800 border-cyan-200",
  action_completed: "bg-teal-100 text-teal-800 border-teal-200",
  verified: "bg-emerald-100 text-emerald-800 border-emerald-200",
  recovered: "bg-green-100 text-green-800 border-green-200",
  false_positive: "bg-gray-100 text-gray-800 border-gray-200",
  legitimate_exception: "bg-indigo-100 text-indigo-800 border-indigo-200",
  closed: "bg-gray-100 text-gray-500 border-gray-200",
};

function statusLabel(status: string): string {
  return status
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function SeverityBadge({ severity }: { severity: Severity | null }) {
  if (!severity) return <span className="text-gray-400">—</span>;
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${severityColors[severity] || "bg-gray-100 text-gray-800"}`}
    >
      {severity.charAt(0).toUpperCase() + severity.slice(1)}
    </span>
  );
}

export function StatusBadge({ status }: { status: CaseStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${statusColors[status] || "bg-gray-100 text-gray-800"}`}
    >
      {statusLabel(status)}
    </span>
  );
}
