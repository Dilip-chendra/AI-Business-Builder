"use client";

import { SWRConfig } from "swr";
import { apiRequest } from "./api";

export const fetcher = (path: string) => apiRequest(path);

export function SWRProvider({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig
      value={{
        fetcher,
        revalidateOnFocus: false,
        shouldRetryOnError: false,
      }}
    >
      {children}
    </SWRConfig>
  );
}
