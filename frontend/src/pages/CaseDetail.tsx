import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  UserPlus,
  Clock,
  FileText,
  DollarSign,
  Shield,
  Loader2,
} from "lucide-react";
import {
  useLeakageCase,
  useRecoveryDrafts,
  useApproveCase,
  useRejectCase,
  useAssignCase,
  useCloseCase,
  useCreateRecoveryDraft,
} from "../api/hooks/useQueries";
import { useAuth } from "../api/hooks/useAuth";
import { SeverityBadge, StatusBadge } from "../components/StatusBadge";
import {
  formatCurrency,
  formatPercent,
  formatDateTime,
  leakageTypeLabel,
} from "../lib/utils";

function ActionButton({
  onClick,
  icon: Icon,
  label,
  color,
  disabled,
  loading,
}: {
  onClick: () => void;
  icon: typeof CheckCircle2;
  label: string;
  color: string;
  disabled?: boolean;
  loading?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors disabled:opacity-50 ${color}`}
    >
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <Icon className="h-4 w-4" />
      )}
      {label}
    </button>
  );
}

export function CaseDetail() {
  const { id } = useParams<{ id: string }>();
  const { userRole } = useAuth();
  const { data: caseData, isLoading, error } = useLeakageCase(id || "");
  const { data: drafts } = useRecoveryDrafts(id || "");
  const approveCase = useApproveCase();
  const rejectCase = useRejectCase();
  const assignCase = useAssignCase();
  const closeCase = useCloseCase();
  const createDraft = useCreateRecoveryDraft();

  const [rejectReason, setRejectReason] = useState("");
  const [showReject, setShowReject] = useState(false);
  const [assignee, setAssignee] = useState("");
  const [showAssign, setShowAssign] = useState(false);

  const canApprove = ["Owner", "Admin", "Finance Manager", "Accountant"].includes(
    userRole || ""
  );

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-sm text-gray-500">Loading case details...</div>
      </div>
    );
  }

  if (error || !caseData) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
        <AlertTriangle className="mx-auto mb-2 h-8 w-8 text-red-400" />
        <p className="text-sm text-red-700">Case not found or access denied</p>
        <Link
          to="/inbox"
          className="mt-3 inline-block text-sm font-medium text-blue-600 hover:text-blue-700"
        >
          ← Back to Inbox
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link
            to="/inbox"
            className="mb-2 flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Inbox
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">
            {caseData.case_number}
          </h1>
          <div className="mt-2 flex items-center gap-3">
            <StatusBadge status={caseData.status} />
            <SeverityBadge severity={caseData.severity} />
            <span className="text-sm text-gray-500">
              {leakageTypeLabel(caseData.leakage_type)}
            </span>
          </div>
        </div>

        {/* Actions */}
        {canApprove &&
          ["detected", "investigating", "pending_review"].includes(
            caseData.status
          ) && (
            <div className="flex items-center gap-2">
              <ActionButton
                onClick={() => approveCase.mutate({ id: id! })}
                icon={CheckCircle2}
                label="Approve"
                color="bg-green-600 hover:bg-green-700"
                loading={approveCase.isPending}
              />
              <ActionButton
                onClick={() => setShowReject(!showReject)}
                icon={XCircle}
                label="Reject"
                color="bg-red-600 hover:bg-red-700"
              />
              <ActionButton
                onClick={() => setShowAssign(!showAssign)}
                icon={UserPlus}
                label="Assign"
                color="bg-gray-600 hover:bg-gray-700"
              />
              <ActionButton
                onClick={() => closeCase.mutate(id!)}
                icon={Clock}
                label="Close"
                color="bg-gray-500 hover:bg-gray-600"
                loading={closeCase.isPending}
              />
            </div>
          )}
      </div>

      {/* Reject form */}
      {showReject && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4">
          <label className="mb-2 block text-sm font-medium text-red-700">
            Rejection Reason (required)
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Enter reason for rejection..."
              className="flex-1 rounded-lg border border-red-300 px-3 py-2 text-sm"
            />
            <button
              onClick={() => {
                if (rejectReason.trim()) {
                  rejectCase.mutate(
                    { id: id!, reason: rejectReason },
                    { onSuccess: () => { setShowReject(false); setRejectReason(""); } }
                  );
                }
              }}
              disabled={!rejectReason.trim() || rejectCase.isPending}
              className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              Confirm Rejection
            </button>
          </div>
        </div>
      )}

      {/* Assign form */}
      {showAssign && (
        <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
          <label className="mb-2 block text-sm font-medium text-gray-700">
            Assign to User ID
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={assignee}
              onChange={(e) => setAssignee(e.target.value)}
              placeholder="Enter user ID..."
              className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
            <button
              onClick={() => {
                if (assignee.trim()) {
                  assignCase.mutate(
                    { id: id!, user_id: assignee },
                    { onSuccess: () => { setShowAssign(false); setAssignee(""); } }
                  );
                }
              }}
              disabled={!assignee.trim() || assignCase.isPending}
              className="rounded-lg bg-gray-600 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50"
            >
              Assign
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Main content */}
        <div className="space-y-6 lg:col-span-2">
          {/* Summary */}
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
              <DollarSign className="h-5 w-5 text-gray-400" />
              Financial Summary
            </h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-gray-500">Potential Leakage</p>
                <p className="text-xl font-bold text-red-600">
                  {formatCurrency(caseData.potential_leakage)}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Confidence</p>
                <p className="text-xl font-bold text-gray-900">
                  {formatPercent(
                    caseData.confidence
                      ? parseFloat(caseData.confidence)
                      : null
                  )}
                </p>
              </div>
            </div>
          </div>

          {/* Evidence */}
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
              <FileText className="h-5 w-5 text-gray-400" />
              Evidence
            </h2>
            <p className="text-sm text-gray-500">
              Evidence records will appear here once the Investigation Agent
              gathers them during the investigation phase.
            </p>
          </div>

          {/* Agent Explanation */}
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
              <Shield className="h-5 w-5 text-gray-400" />
              Why Was This Detected?
            </h2>
            <p className="text-sm text-gray-500">
              The Investigation Agent&apos;s analysis and explanation will appear
              here once the case has been investigated.
            </p>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Case info */}
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-gray-900">
              Case Details
            </h3>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-gray-500">Customer</dt>
                <dd className="font-medium text-gray-900">
                  {caseData.customer_name || caseData.customer_id || "—"}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Created</dt>
                <dd className="text-gray-900">
                  {formatDateTime(caseData.created_at)}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-gray-500">Assigned To</dt>
                <dd className="text-gray-900">
                  {caseData.assigned_to || "Unassigned"}
                </dd>
              </div>
            </dl>
          </div>

          {/* Recovery Drafts */}
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-gray-900">
              Recovery Action
            </h3>
            {drafts && drafts.length > 0 ? (
              <div className="space-y-3">
                {drafts.map((draft) => (
                  <div
                    key={draft.draft_id}
                    className="rounded-lg border border-gray-200 p-3"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-gray-900">
                        {draft.action_type.replace(/_/g, " ")}
                      </span>
                      <StatusBadge status={draft.status as never} />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div>
                <p className="mb-3 text-sm text-gray-500">
                  No recovery action drafted yet
                </p>
                {["approved", "action_pending"].includes(caseData.status) && (
                  <button
                    onClick={() => createDraft.mutate(id!)}
                    disabled={createDraft.isPending}
                    className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    {createDraft.isPending
                      ? "Creating..."
                      : "Create Recovery Draft"}
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Timeline */}
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-gray-900">
              Timeline
            </h3>
            <div className="space-y-3">
              <div className="flex items-start gap-3">
                <div className="mt-1 h-2 w-2 rounded-full bg-blue-500" />
                <div>
                  <p className="text-sm text-gray-900">Case detected</p>
                  <p className="text-xs text-gray-500">
                    {formatDateTime(caseData.created_at)}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
