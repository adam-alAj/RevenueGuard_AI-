import { useState } from "react";
import type { ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  Inbox,
  Users,
  RotateCcw,
  Upload,
  Search,
  LogOut,
  ChevronLeft,
  Menu,
  Shield,
} from "lucide-react";
import { useAuth } from "../api/hooks/useAuth";
import { useSearch } from "../api/hooks/useQueries";

const navItems = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/inbox", label: "Leakage Inbox", icon: Inbox },
  { path: "/customers", label: "Customers", icon: Users },
  { path: "/recovery", label: "Recovery Center", icon: RotateCcw },
  { path: "/imports", label: "Imports", icon: Upload },
];

export function Layout({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { logout, userRole } = useAuth();
  const searchResults = useSearch(searchQuery);

  const canApprove = ["Owner", "Admin", "Finance Manager", "Accountant"].includes(
    userRole || ""
  );

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside
        className={`${sidebarOpen ? "w-60" : "w-16"} flex flex-col border-r border-gray-200 bg-white transition-all duration-200`}
      >
        {/* Logo */}
        <div className="flex h-14 items-center border-b border-gray-200 px-4">
          {sidebarOpen ? (
            <Link to="/" className="flex items-center gap-2">
              <Shield className="h-6 w-6 text-blue-600" />
              <span className="text-lg font-bold text-gray-900">
                RevenueGuard
              </span>
            </Link>
          ) : (
            <Shield className="mx-auto h-6 w-6 text-blue-600" />
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 px-2 py-4">
          {navItems.map((item) => {
            const isActive =
              item.path === "/"
                ? location.pathname === "/"
                : location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-blue-50 text-blue-700"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`}
                title={item.label}
              >
                <item.icon className="h-5 w-5 flex-shrink-0" />
                {sidebarOpen && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* User section */}
        <div className="border-t border-gray-200 px-3 py-3">
          {sidebarOpen && (
            <div className="mb-2 text-xs text-gray-500">
              Role: {userRole || "Unknown"}
            </div>
          )}
          <button
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 hover:text-gray-900"
            title="Sign out"
          >
            <LogOut className="h-5 w-5 flex-shrink-0" />
            {sidebarOpen && <span>Sign out</span>}
          </button>
        </div>

        {/* Toggle */}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="border-t border-gray-200 px-3 py-2 text-gray-500 hover:text-gray-700"
        >
          {sidebarOpen ? (
            <ChevronLeft className="mx-auto h-4 w-4" />
          ) : (
            <Menu className="mx-auto h-4 w-4" />
          )}
        </button>
      </aside>

      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-6">
          <div className="flex items-center gap-4">
            {/* Search */}
            <div className="relative">
              <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5">
                <Search className="h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search cases, customers..."
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setSearchOpen(e.target.value.length >= 2);
                  }}
                  onFocus={() => setSearchOpen(searchQuery.length >= 2)}
                  onBlur={() => setTimeout(() => setSearchOpen(false), 200)}
                  className="w-64 bg-transparent text-sm outline-none placeholder:text-gray-400"
                />
              </div>

              {/* Search dropdown */}
              {searchOpen && searchResults.data && (
                <div className="absolute top-full left-0 z-50 mt-1 w-96 rounded-lg border border-gray-200 bg-white shadow-lg">
                  {searchResults.data.items.length === 0 ? (
                    <div className="p-4 text-sm text-gray-500">
                      No results found
                    </div>
                  ) : (
                    <div className="max-h-80 overflow-y-auto">
                      {searchResults.data.items.map((item) => (
                        <button
                          key={`${item.entity_type}-${item.entity_id}`}
                          onClick={() => {
                            const routes: Record<string, string> = {
                              customer: `/customers/${item.entity_id}`,
                              contract: `/customers`,
                              invoice: `/customers`,
                              case: `/case/${item.entity_id}`,
                            };
                            navigate(routes[item.entity_type] || "/");
                            setSearchOpen(false);
                            setSearchQuery("");
                          }}
                          className="flex w-full items-center gap-3 border-b border-gray-100 px-4 py-3 text-left hover:bg-gray-50"
                        >
                          <div className="flex-1">
                            <div className="text-sm font-medium text-gray-900">
                              {item.title}
                            </div>
                            {item.subtitle && (
                              <div className="text-xs text-gray-500">
                                {item.subtitle}
                              </div>
                            )}
                          </div>
                          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                            {item.entity_type}
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-3">
            {canApprove && (
              <span className="flex items-center gap-1 text-xs text-gray-500">
                <Shield className="h-3 w-3" /> {userRole}
              </span>
            )}
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto bg-gray-50 p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
