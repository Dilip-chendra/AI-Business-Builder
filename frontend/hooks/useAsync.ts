"use client";

import { useCallback, useRef, useState } from "react";

/**
 * Wraps an async function with loading and error state.
 *
 * The `fn` argument is captured in a ref so callers don't need to memoize it —
 * the hook always calls the latest version without triggering re-renders.
 */
export function useAsync<TArgs extends unknown[], TResult>(fn: (...args: TArgs) => Promise<TResult>) {
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async (...args: TArgs): Promise<TResult> => {
    setLoading(true);
    setError(null);
    try {
      return await fnRef.current(...args);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []); // stable reference — never changes

  return { run, loading, error };
}
