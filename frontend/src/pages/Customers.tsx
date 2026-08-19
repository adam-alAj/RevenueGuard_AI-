import { useState } from "react";
import { Link } from "react-router-dom";
import { Users, Search, ExternalLink } from "lucide-react";
import { useCustomers } from "../api/hooks/useQueries";

export function Customers() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const { data, isLoading } = useCustomers({ page, page_size: 20, search });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Customers</h1>
          <p className="mt-1 text-sm text-gray-500">
            {data?.total ?? 0} customers
          </p>
        </div>
      </div>

      {/* Search */}
      <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2">
        <Search className="h-4 w-4 text-gray-400" />
        <input
          type="text"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          placeholder="Search customers..."
          className="flex-1 bg-transparent text-sm outline-none"
        />
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">
                Name
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">
                Email
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">
                Company
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">
                Status
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium text-gray-500">
                Health
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {isLoading ? (
              <tr>
                <td
                  colSpan={5}
                  className="px-4 py-12 text-center text-sm text-gray-500"
                >
                  Loading...
                </td>
              </tr>
            ) : data?.items.length === 0 ? (
              <tr>
                <td
                  colSpan={5}
                  className="px-4 py-12 text-center text-sm text-gray-500"
                >
                  {search
                    ? "No customers match your search"
                    : "No customers found. Import data to get started."}
                </td>
              </tr>
            ) : (
              data?.items.map((customer) => (
                <tr key={customer.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Users className="h-4 w-4 text-gray-400" />
                      <span className="text-sm font-medium text-gray-900">
                        {customer.name}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {customer.email || "—"}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {customer.company || "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        customer.is_active
                          ? "bg-green-100 text-green-800"
                          : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {customer.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <Link
                      to={`/customers/${customer.id}`}
                      className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700"
                    >
                      <ExternalLink className="h-3 w-3" />
                      Health
                    </Link>
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
                Previous
              </button>
              <button
                onClick={() => setPage(Math.min(data.total_pages, page + 1))}
                disabled={page >= data.total_pages}
                className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
