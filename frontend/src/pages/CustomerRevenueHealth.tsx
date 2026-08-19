import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  AlertTriangle,
  TrendingUp,
  DollarSign,
  FileText,
  CreditCard,
  AlertCircle,
} from "lucide-react";
import { useCustomer, useRevenueHealth } from "../api/hooks/useQueries";
import { formatCurrency } from "../lib/utils";

function MetricBlock({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: string;
  icon: typeof DollarSign;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-3">
        <div className={`rounded-lg p-2 ${color}`}>
          <Icon className="h-5 w-5 text-white" />
        </div>
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className="text-xl font-bold text-gray-900">{value}</p>
        </div>
      </div>
    </div>
  );
}

export function CustomerRevenueHealth() {
  const { id } = useParams<{ id: string }>();
  const { data: customer, isLoading: loadingCustomer } = useCustomer(id || "");
  const { data: health, isLoading: loadingHealth, error } =
    useRevenueHealth(id || "");

  if (loadingCustomer || loadingHealth) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-sm text-gray-500">Loading customer data...</div>
      </div>
    );
  }

  if (error || !customer) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
        <AlertTriangle className="mx-auto mb-2 h-8 w-8 text-red-400" />
        <p className="text-sm text-red-700">Customer not found</p>
        <Link
          to="/customers"
          className="mt-3 inline-block text-sm font-medium text-blue-600 hover:text-blue-700"
        >
          ← Back to Customers
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link
          to="/customers"
          className="mb-2 flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Customers
        </Link>
        <h1 className="text-2xl font-bold text-gray-900">{customer.name}</h1>
        <p className="mt-1 text-sm text-gray-500">Revenue Health Overview</p>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricBlock
          label="Contract Value"
          value={formatCurrency(health?.total_contract_value)}
          icon={FileText}
          color="bg-blue-500"
        />
        <MetricBlock
          label="Total Invoiced"
          value={formatCurrency(health?.total_invoiced)}
          icon={DollarSign}
          color="bg-purple-500"
        />
        <MetricBlock
          label="Total Paid"
          value={formatCurrency(health?.total_paid)}
          icon={CreditCard}
          color="bg-green-500"
        />
        <MetricBlock
          label="Outstanding"
          value={formatCurrency(health?.total_outstanding)}
          icon={AlertCircle}
          color="bg-amber-500"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Leakage Summary */}
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
            <TrendingUp className="h-5 w-5 text-gray-400" />
            Leakage Summary
          </h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between rounded-lg bg-red-50 p-4">
              <span className="text-sm font-medium text-red-700">
                Potential Leakage
              </span>
              <span className="text-lg font-bold text-red-600">
                {formatCurrency(health?.potential_leakage)}
              </span>
            </div>
            <div className="flex items-center justify-between rounded-lg bg-green-50 p-4">
              <span className="text-sm font-medium text-green-700">
                Recovered Revenue
              </span>
              <span className="text-lg font-bold text-green-600">
                {formatCurrency(health?.recovery_history)}
              </span>
            </div>
            <div className="flex items-center justify-between rounded-lg bg-gray-50 p-4">
              <span className="text-sm text-gray-600">
                Active Subscriptions
              </span>
              <span className="font-medium text-gray-900">
                {health?.active_subscriptions ?? 0}
              </span>
            </div>
            <div className="flex items-center justify-between rounded-lg bg-gray-50 p-4">
              <span className="text-sm text-gray-600">Billing Anomalies</span>
              <span className="font-medium text-gray-900">
                {health?.billing_anomalies ?? 0}
              </span>
            </div>
          </div>
        </div>

        {/* Customer Details */}
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">
            Customer Details
          </h2>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Email</dt>
              <dd className="text-gray-900">{customer.email || "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Phone</dt>
              <dd className="text-gray-900">{customer.phone || "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Company</dt>
              <dd className="text-gray-900">{customer.company || "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">External ID</dt>
              <dd className="text-gray-900">
                {customer.external_id || "—"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Status</dt>
              <dd>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    customer.is_active
                      ? "bg-green-100 text-green-800"
                      : "bg-gray-100 text-gray-600"
                  }`}
                >
                  {customer.is_active ? "Active" : "Inactive"}
                </span>
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
}
