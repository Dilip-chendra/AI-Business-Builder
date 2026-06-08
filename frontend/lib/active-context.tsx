"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { useAuth } from "./auth-context";
import type { Business } from "./types";

type Workspace = Record<string, any> & { id: string; name: string };
type Project = Record<string, any> & { id: string; name: string };
type Active = { workspace_id: string | null; business_id: string | null; project_id: string | null };
type ActiveContextPayload = Partial<Active>;

type ActiveContextValue = {
  active: Active;
  workspaces: Workspace[];
  businesses: Business[];
  projects: Project[];
  activeWorkspace: Workspace | null;
  activeBusiness: Business | null;
  activeProject: Project | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  setActiveContext: (payload: ActiveContextPayload) => Promise<void>;
};

const emptyActive: Active = { workspace_id: null, business_id: null, project_id: null };
const ActiveContext = createContext<ActiveContextValue | null>(null);

export function ActiveContextProvider({ children }: { children: React.ReactNode }) {
  const { user, isLoading: authLoading } = useAuth();
  const [active, setActive] = useState<Active>(emptyActive);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const applyPayload = (payload: any) => {
    const nextBusinesses = payload?.businesses || [];
    const nextActive = { ...emptyActive, ...(payload?.active || {}) };
    if (!nextActive.business_id && nextBusinesses[0]?.id) {
      nextActive.business_id = nextBusinesses[0].id;
      nextActive.workspace_id = nextActive.workspace_id || nextBusinesses[0].workspace_id || null;
      nextActive.project_id = nextActive.project_id || nextBusinesses[0].project_id || null;
    }
    const activeBusiness = nextBusinesses.find((item: Business) => item.id === nextActive.business_id);
    if (activeBusiness) {
      nextActive.workspace_id = activeBusiness.workspace_id || nextActive.workspace_id || null;
      nextActive.project_id = activeBusiness.project_id || null;
    }
    setActive(nextActive);
    setWorkspaces(payload?.workspaces || []);
    setBusinesses(nextBusinesses);
    setProjects(payload?.projects || []);
  };

  const refresh = async () => {
    if (!user) {
      applyPayload({ active: emptyActive, workspaces: [], businesses: [], projects: [] });
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const payload = await api.getActiveContext();
      if ((!payload?.businesses || payload.businesses.length === 0) && user) {
        const allBusinesses = await api.listBusinesses().catch(() => []);
        applyPayload({ ...payload, businesses: allBusinesses });
      } else {
        applyPayload(payload);
      }
    } catch (err: any) {
      const fallbackBusinesses = await api.listBusinesses().catch(() => []);
      if (fallbackBusinesses.length > 0) {
        setError(null);
        applyPayload({ active: emptyActive, workspaces: [], businesses: fallbackBusinesses, projects: [] });
      } else {
        setError(err?.message || "Could not load workspace context.");
        applyPayload({ active: emptyActive, workspaces: [], businesses: [], projects: [] });
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!authLoading) void refresh();
  }, [authLoading, user?.id]);

  const setActiveContext = async (payload: ActiveContextPayload) => {
    const selectedBusiness = payload.business_id
      ? businesses.find((item) => item.id === payload.business_id)
      : null;
    const normalizedPayload = selectedBusiness
      ? {
          ...payload,
          workspace_id: payload.workspace_id || selectedBusiness.workspace_id || null,
          project_id: selectedBusiness.project_id || null,
        }
      : payload;
    const response = await api.setActiveContext(normalizedPayload);
    setActive({ ...emptyActive, ...(response?.active || {}) });
    await refresh();
  };

  const value = useMemo<ActiveContextValue>(() => {
    const activeWorkspace = workspaces.find((item) => item.id === active.workspace_id) || null;
    const activeBusiness = businesses.find((item) => item.id === active.business_id) || null;
    const activeProject = projects.find((item) => item.id === active.project_id) || null;
    return {
      active,
      workspaces,
      businesses,
      projects,
      activeWorkspace,
      activeBusiness,
      activeProject,
      isLoading,
      error,
      refresh,
      setActiveContext,
    };
  }, [active, workspaces, businesses, projects, isLoading, error]);

  return <ActiveContext.Provider value={value}>{children}</ActiveContext.Provider>;
}

export function useActiveContext() {
  const context = useContext(ActiveContext);
  if (!context) throw new Error("useActiveContext must be used inside ActiveContextProvider");
  return context;
}
