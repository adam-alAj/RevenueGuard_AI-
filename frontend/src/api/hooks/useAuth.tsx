import { useState, useEffect, useCallback, createContext, useContext } from "react";
import type { ReactNode } from "react";
import * as client from "../client";

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    orgName: string,
    email: string,
    password: string,
    name: string
  ) => Promise<void>;
  logout: () => void;
  userRole: string | null;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(
    client.isAuthenticated()
  );
  const [isLoading, setIsLoading] = useState(false);
  const [userRole, setUserRole] = useState<string | null>(null);

  useEffect(() => {
    // Try to decode role from JWT payload
    const token = localStorage.getItem("access_token");
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        setUserRole(payload.role || null);
      } catch {
        setUserRole(null);
      }
    }
  }, [isAuthenticated]);

  const login = useCallback(async (email: string, password: string) => {
    setIsLoading(true);
    try {
      await client.login(email, password);
      setIsAuthenticated(true);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const register = useCallback(
    async (
      orgName: string,
      email: string,
      password: string,
      name: string
    ) => {
      setIsLoading(true);
      try {
        await client.register(orgName, email, password, name);
        setIsAuthenticated(true);
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const logout = useCallback(() => {
    client.logout();
    setIsAuthenticated(false);
    setUserRole(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{ isAuthenticated, isLoading, login, register, logout, userRole }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
