import {
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  DollarSign,
  FileCheck,
  Clock,
} from "lucide-react";
import { useOrgMetrics } from "../api/hooks/useQueries";
import { formatCurrency, formatPercent } from "../lib/utils";

function MetricCard({
  label,
  value,
  icon: Icon,
  color,
  subtext,
}: {
  label: string;
  value: string;
  icon: typeof DollarSign;
  color: string;
  subtext?: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500">{label}</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">{value}</p>
          {subtext && (
            <p className="mt-0.5 text-xs text-gray-400">{subtext}</p>
          )}
        </div>
        <div className={`rounded-lg p-3 ${color}`}>
          <Icon className="h-5 w-5 text-white" />
        </div>
      </div>
    </div>
  );
}

export function Dashboard() {
  const { data: metrics, isLoading, error } = useOrgMetrics();

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-sm text-gray-500">Loading dashboard...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
        <AlertTriangle className="mx-auto mb-2 h-8 w-8 text-red-400" />
        <p className="text-sm text-red-700">
          Unable to load dashboard metrics. Make sure you&apos;re connected to
          the backend.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Executive Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Revenue leakage detection overview
        </p>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <MetricCard
          label="Potential Leakage"
          value={formatCurrency(metrics?.total_potential_leakage)}
          icon={TrendingUp}
          color="bg-red-500"
          subtext="Total detected across all cases"
        />
        <MetricCard
          label="Recovered Revenue"
          value={formatCurrency(metrics?.total_recovered_revenue)}
          icon={TrendingDown}
          color="bg-green-500"
          subtext="Successfully recovered"
        />
        <MetricCard
          label="Recovery Rate"
          value={formatPercent(metrics?.recovery_rate)}
          icon={FileCheck}
          color="bg-blue-500"
          subtext="Of potential leakage recovered"
        />
        <MetricCard
          label="Open Cases"
          value={String(metrics?.open_cases ?? 0)}
          icon={Clock}
          color="bg-amber-500"
          subtext="Awaiting action"
        />
        <MetricCard
          label="Critical Cases"
          value={String(metrics?.critical_cases ?? 0)}
          icon={AlertTriangle}
          color="bg-red-600"
          subtext="Requiring immediate attention"
        />
        <MetricCard
          label="Confirmed Leakage"
          value={formatCurrency(metrics?.total_confirmed_leakage)}
          icon={DollarSign}
          color="bg-purple-500"
          subtext="Verified by investigation"
        />
      </div>

      {/* Pipeline overview */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          Recovery Pipeline
        </h2>
        <div className="flex items-center gap-2">
          {[
            {
              label: "Detected",
              count: metrics?.open_cases ?? 0,
              color: "bg-blue-500",
            },
            {
              label: "Investigating",
              count: 0,
              color: "bg-purple-500",
            },
            {
              label: "Pending Review",
              count: 0,
              color: "bg-amber-500",
            },
            {
              label: "Approved",
              count: 0,
              color: "bg-green-500",
            },
            {
              label: "Recovered",
              count: 0,
              color: "bg-emerald-600",
            },
          ].map((stage) => (
            <div key={stage.label} className="flex-1">
              <div className="flex items-center gap-2">
                <div className={`h-2 w-full rounded-full ${stage.color}`} />
                <span className="text-sm font-medium text-gray-700">
                  {stage.count}
                </span>
              </div>
              <p className="mt-1 text-xs text-gray-500">{stage.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <a
          href="/inbox"
          className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-colors hover:border-blue-200 hover:bg-blue-50"
        >
          <h3 className="font-semibold text-gray-900">Leakage Inbox</h3>
          <p className="mt-1 text-sm text-gray-500">
            Review detected cases and take action
          </p>
        </a>
        <a
          href="/recovery"
          className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-colors hover:border-green-200 hover:bg-green-50"
        >
          <h3 className="font-semibold text-gray-900">Recovery Center</h3>
          <p className="mt-1 text-sm text-gray-500">
            Track recovery progress and draft actions
          </p>
        </a>
        <a
          href="/imports"
          className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-colors hover:border-purple-200 hover:bg-purple-50"
        >
          <h3 className="font-semibold text-gray-900">Import Data</h3>
          <p className="mt-1 text-sm text-gray-500">
            Upload CSV/Excel files to update data
          </p>
        </a>
      </div>
    </div>
  );
}
