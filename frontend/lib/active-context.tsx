"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import type { ActiveContext, Business, Project, Workspace } from "@/lib/types";
import { useAuth } from "@/lib/auth-context";

type ActiveContextValue = {
  active: ActiveContext;
  workspaces: Workspace[];
  businesses: Business[];
  projects: Project[];
  isLoading: boolean;
  refresh: () => Promise<void>;
  setActiveContext: (payload: Partial<ActiveContext>) => Promise<void>;
  activeBusiness: Business | null;
  activeWorkspace: Workspace | null;
  activeProject: Project | null;
};

const ActiveContextContext = createContext<ActiveContextValue | undefined>(undefined);

const EMPTY_CONTEXT: ActiveContext = {
  workspace_id: null,
  business_id: null,
  project_id: null,
};

export function ActiveContextProvider({ children }: { children: React.ReactNode }) {
  const { user, isLoading: authLoading } = useAuth();
  const [active, setActive] = useState<ActiveContext>(EMPTY_CONTEXT);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const refresh = async () => {
    if (!user) {
      setActive(EMPTY_CONTEXT);
      setWorkspaces([]);
      setBusinesses([]);
      setProjects([]);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const hierarchy = await api.getActiveContext();
      setActive(hierarchy.active);
      setWorkspaces(hierarchy.workspaces);
      setBusinesses(hierarchy.businesses);
      setProjects(hierarchy.projects);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!authLoading) {
      refresh().catch(console.error);
    }
  }, [authLoading, user?.id]);

  const setActiveContext = async (payload: Partial<ActiveContext>) => {
    const next = { ...active, ...payload };
    await api.setActiveContext(next);
    await refresh();
  };

  const value = useMemo<ActiveContextValue>(() => ({
    active,
    workspaces,
    businesses,
    projects,
    isLoading: authLoading || isLoading,
    refresh,
    setActiveContext,
    activeBusiness: businesses.find((item) => item.id === active.business_id) || null,
    activeWorkspace: workspaces.find((item) => item.id === active.workspace_id) || null,
    activeProject: projects.find((item) => item.id === active.project_id) || null,
  }), [active, workspaces, businesses, projects, authLoading, isLoading]);

  return <ActiveContextContext.Provider value={value}>{children}</ActiveContextContext.Provider>;
}

export function useActiveContext() {
  const context = useContext(ActiveContextContext);
  if (!context) {
    throw new Error("useActiveContext must be used within ActiveContextProvider");
  }
  return context;
}
