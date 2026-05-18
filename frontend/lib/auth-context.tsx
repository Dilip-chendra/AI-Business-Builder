"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { api } from "@/lib/api";

type User = {
  id: string;
  email: string;
  full_name: string;
};

type AuthContextType = {
  user: User | null;
  isLoading: boolean;
  login: (token: string, redirect?: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  const publicRoutes = ["/", "/login", "/signup", "/ai-status"];
  const isPublicRoute = publicRoutes.includes(pathname) || pathname.startsWith("/landing/") || pathname.startsWith("/checkout/");

  useEffect(() => {
    const initializeAuth = async () => {
      const token = localStorage.getItem("access_token");
      if (token) {
        try {
          const userData = await api.me();
          setUser(userData);
        } catch (error) {
          console.error("Invalid or expired token", error);
          localStorage.removeItem("access_token");
          setUser(null);
        }
      }
      setIsLoading(false);
    };

    initializeAuth();
  }, []);

  useEffect(() => {
    // Route protection redirect
    if (!isLoading && !user && !isPublicRoute) {
      router.push("/login");
    }
  }, [user, isLoading, pathname, isPublicRoute, router]);

  const login = async (token: string, redirect: string = "/dashboard") => {
    localStorage.setItem("access_token", token);
    try {
      const userData = await api.me();
      setUser(userData);
      router.push(redirect);
    } catch (error) {
      console.error("Failed to fetch user data after login", error);
      localStorage.removeItem("access_token");
      throw new Error("Failed to verify login credentials");
    }
  };

  const logout = () => {
    localStorage.removeItem("access_token");
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
