import { useState } from "react";
import {
  Upload,
  FileText,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import { useUploadImport, useImportJob } from "../api/hooks/useQueries";

const entityTypes = [
  { value: "customer", label: "Customers" },
  { value: "contract", label: "Contracts" },
  { value: "contract_line", label: "Contract Lines" },
  { value: "project", label: "Projects" },
  { value: "invoice", label: "Invoices" },
  { value: "invoice_line", label: "Invoice Lines" },
  { value: "payment", label: "Payments" },
];

export function Imports() {
  const [file, setFile] = useState<File | null>(null);
  const [targetEntity, setTargetEntity] = useState("customer");
  const [jobHistory, setJobHistory] = useState<string[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const uploadMutation = useUploadImport();
  const { data: jobData } = useImportJob(selectedJobId || "");

  const handleUpload = async () => {
    if (!file) return;
    uploadMutation.mutate(
      { file, targetEntity },
      {
        onSuccess: (job) => {
          setJobHistory((prev) => [job.id, ...prev]);
          setSelectedJobId(job.id);
          setFile(null);
        },
      }
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Import Data</h1>
        <p className="mt-1 text-sm text-gray-500">
          Upload CSV or Excel files to import data into RevenueGuard
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Upload form */}
        <div className="lg:col-span-1">
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
              <Upload className="h-5 w-5 text-gray-400" />
              Upload File
            </h2>

            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  Target Entity
                </label>
                <select
                  value={targetEntity}
                  onChange={(e) => setTargetEntity(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                >
                  {entityTypes.map((et) => (
                    <option key={et.value} value={et.value}>
                      {et.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  File (CSV or Excel)
                </label>
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-blue-50 file:px-3 file:py-1 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100"
                />
              </div>

              {file && (
                <div className="flex items-center gap-2 rounded-lg bg-gray-50 p-3">
                  <FileText className="h-4 w-4 text-gray-400" />
                  <span className="text-sm text-gray-700">{file.name}</span>
                  <span className="text-xs text-gray-400">
                    ({(file.size / 1024).toFixed(1)} KB)
                  </span>
                </div>
              )}

              <button
                onClick={handleUpload}
                disabled={!file || uploadMutation.isPending}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {uploadMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Upload className="h-4 w-4" />
                )}
                {uploadMutation.isPending ? "Uploading..." : "Upload & Import"}
              </button>

              {uploadMutation.isError && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                  Upload failed. Please check the file format and try again.
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Job history & details */}
        <div className="lg:col-span-2">
          {/* Job list */}
          <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-200 px-6 py-4">
              <h2 className="text-lg font-semibold text-gray-900">
                Import History
              </h2>
            </div>

            {jobHistory.length === 0 && !jobData ? (
              <div className="px-6 py-12 text-center text-sm text-gray-500">
                No imports yet. Upload a file to get started.
              </div>
            ) : (
              <div>
                {/* Job list */}
                <div className="divide-y divide-gray-100">
                  {jobHistory.map((jobId) => (
                    <button
                      key={jobId}
                      onClick={() => setSelectedJobId(jobId)}
                      className={`flex w-full items-center justify-between px-6 py-3 text-left hover:bg-gray-50 ${
                        selectedJobId === jobId ? "bg-blue-50" : ""
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <FileText className="h-4 w-4 text-gray-400" />
                        <div>
                          <p className="text-sm font-medium text-gray-900">
                            Import {jobId.slice(0, 8)}
                          </p>
                          <p className="text-xs text-gray-500">
                            {jobId}
                          </p>
                        </div>
                      </div>
                      <span className="text-xs text-gray-400">View</span>
                    </button>
                  ))}
                </div>

                {/* Job details */}
                {jobData && (
                  <div className="border-t border-gray-200 p-6">
                    <h3 className="mb-3 text-sm font-semibold text-gray-900">
                      Import Details
                    </h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="rounded-lg bg-gray-50 p-3">
                        <p className="text-xs text-gray-500">Entity</p>
                        <p className="font-medium text-gray-900">
                          {jobData.target_entity}
                        </p>
                      </div>
                      <div className="rounded-lg bg-gray-50 p-3">
                        <p className="text-xs text-gray-500">Status</p>
                        <div className="flex items-center gap-1">
                          {jobData.status === "completed" ? (
                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                          ) : jobData.status === "failed" ? (
                            <XCircle className="h-4 w-4 text-red-500" />
                          ) : (
                            <AlertTriangle className="h-4 w-4 text-amber-500" />
                          )}
                          <span className="font-medium text-gray-900">
                            {jobData.status}
                          </span>
                        </div>
                      </div>
                      <div className="rounded-lg bg-gray-50 p-3">
                        <p className="text-xs text-gray-500">Imported</p>
                        <p className="font-medium text-green-600">
                          {jobData.records_imported}
                        </p>
                      </div>
                      <div className="rounded-lg bg-gray-50 p-3">
                        <p className="text-xs text-gray-500">Rejected</p>
                        <p
                          className={`font-medium ${
                            jobData.records_rejected > 0
                              ? "text-red-600"
                              : "text-gray-900"
                          }`}
                        >
                          {jobData.records_rejected}
                        </p>
                      </div>
                    </div>

                    {/* Errors */}
                    {jobData.errors && jobData.errors.length > 0 && (
                      <div className="mt-4">
                        <h4 className="mb-2 text-sm font-semibold text-gray-900">
                          Rejected Rows
                        </h4>
                        <div className="max-h-48 overflow-y-auto rounded-lg border border-gray-200">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="border-b border-gray-100 bg-gray-50">
                                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">
                                  Row
                                </th>
                                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">
                                  Reason
                                </th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                              {jobData.errors.map((err, i) => (
                                <tr key={i}>
                                  <td className="px-3 py-2 text-gray-700">
                                    {err.row_number}
                                  </td>
                                  <td className="px-3 py-2 text-red-600">
                                    {err.reason}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
