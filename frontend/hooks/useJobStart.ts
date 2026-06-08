'use client';

import { useState, useCallback } from 'react';

export interface JobResponse {
  job_id: string;
  job_type: string;
  status: string;
  progress_percent: number;
  created_at: string | null;
}

interface UseJobStartOptions {
  onSuccess?: (response: JobResponse) => void;
  onError?: (error: string) => void;
}

/**
 * Hook for starting and managing background jobs
 */
export function useJobStart(options?: UseJobStartOptions) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startSeoBlogJob = useCallback(
    async (businessId: string, topic: string, targetKeyword: string) => {
      setIsLoading(true);
      setError(null);

      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
        const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : '';
        const response = await fetch(
          `${API_URL}/marketing/${businessId}/seo/generate-async`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: JSON.stringify({
              topic,
              target_keyword: targetKeyword,
            }),
          }
        );

        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.detail || 'Failed to start job');
        }

        const data = await response.json();
        options?.onSuccess?.(data);
        return data;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unknown error';
        setError(message);
        options?.onError?.(message);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [options]
  );

  const startEmailCampaignJob = useCallback(
    async (
      businessId: string,
      name: string,
      goal: string,
      recipientCount: number = 0
    ) => {
      setIsLoading(true);
      setError(null);

      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
        const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : '';
        const response = await fetch(
          `${API_URL}/marketing/${businessId}/campaigns/email-async`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: JSON.stringify({
              name,
              goal,
              recipient_count: recipientCount,
            }),
          }
        );

        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.detail || 'Failed to start job');
        }

        const data = await response.json();
        options?.onSuccess?.(data);
        return data;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unknown error';
        setError(message);
        options?.onError?.(message);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [options]
  );

  const startCodeEditJob = useCallback(
    async (instruction: string, maxTokens: number = 2000) => {
      setIsLoading(true);
      setError(null);

      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
        const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : '';
        const response = await fetch(`${API_URL}/jobs/start`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            job_type: 'code_edit',
            job_name: `Code edit: ${instruction.substring(0, 50)}...`,
            job_description: 'AI-assisted code transformation',
            payload: {
              instruction,
              max_tokens: maxTokens,
            },
            estimated_completion_seconds: 90,
          }),
        });

        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.detail || 'Failed to start job');
        }

        const data = await response.json();
        options?.onSuccess?.(data);
        return data;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Unknown error';
        setError(message);
        options?.onError?.(message);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [options]
  );

  return {
    startSeoBlogJob,
    startEmailCampaignJob,
    startCodeEditJob,
    isLoading,
    error,
  };
}

export default useJobStart;
