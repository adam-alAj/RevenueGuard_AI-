import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "./api/hooks/useAuth";
import { Layout } from "./components/Layout";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { LeakageInbox } from "./pages/LeakageInbox";
import { CaseDetail } from "./pages/CaseDetail";
import { Customers } from "./pages/Customers";
import { CustomerRevenueHealth } from "./pages/CustomerRevenueHealth";
import { RecoveryCenter } from "./pages/RecoveryCenter";
import { Imports } from "./pages/Imports";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <Layout>{children}</Layout>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <AuthGuard>
            <Dashboard />
          </AuthGuard>
        }
      />
      <Route
        path="/inbox"
        element={
          <AuthGuard>
            <LeakageInbox />
          </AuthGuard>
        }
      />
      <Route
        path="/case/:id"
        element={
          <AuthGuard>
            <CaseDetail />
          </AuthGuard>
        }
      />
      <Route
        path="/customers"
        element={
          <AuthGuard>
            <Customers />
          </AuthGuard>
        }
      />
      <Route
        path="/customers/:id"
        element={
          <AuthGuard>
            <CustomerRevenueHealth />
          </AuthGuard>
        }
      />
      <Route
        path="/recovery"
        element={
          <AuthGuard>
            <RecoveryCenter />
          </AuthGuard>
        }
      />
      <Route
        path="/imports"
        element={
          <AuthGuard>
            <Imports />
          </AuthGuard>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
