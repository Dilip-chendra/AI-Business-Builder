'use client';

import { useState, useEffect } from 'react';
import { CheckCircle, XCircle, Loader2, Clock } from 'lucide-react';

export interface JobStatus {
  id: string;
  job_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  job_name: string;
  progress_percent: number;
  progress_message: string | null;
  result: Record<string, any>;
  error_message: string | null;
  created_at: string | null;
  completed_at: string | null;
  estimated_completion_seconds: number | null;
}

interface JobProgressProps {
  jobId: string;
  onComplete?: (result: Record<string, any>) => void;
  onError?: (error: string) => void;
  refreshInterval?: number;
}

export function JobProgress({ jobId, onComplete, onError, refreshInterval = 2000 }: JobProgressProps) {
  const [job, setJob] = useState<JobStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    let intervalId: ReturnType<typeof setInterval> | null = null;

    const fetchJob = async () => {
      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
        const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : '';
        const response = await fetch(`${API_URL}/jobs/${jobId}`, {
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data: JobStatus = await response.json();

        if (isMounted) {
          setJob(data);
          setLoading(false);
          if (data.status === 'completed') {
            onComplete?.(data.result);
            if (intervalId) clearInterval(intervalId);
          }
          if (data.status === 'failed') {
            const msg = data.error_message || 'Job failed';
            setError(msg);
            onError?.(msg);
            if (intervalId) clearInterval(intervalId);
          }
        }
      } catch (err) {
        if (isMounted) {
          const message = err instanceof Error ? err.message : 'Unknown error';
          setError(message);
          onError?.(message);
        }
      }
    };

    fetchJob();
    intervalId = setInterval(fetchJob, refreshInterval);
    return () => { isMounted = false; if (intervalId) clearInterval(intervalId); };
  }, [jobId, refreshInterval, onComplete, onError]);

  if (loading) {
    return (
      <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <Loader2 size={18} style={{ color: '#6366f1', animation: 'spin 1s linear infinite', flexShrink: 0 }} />
        <div style={{ flex: 1 }}>
          <div style={{ height: 12, background: '#f1f5f9', borderRadius: 6, marginBottom: 8, animation: 'pulse 1.5s infinite' }} />
          <div style={{ height: 8, background: '#f1f5f9', borderRadius: 6, width: '60%', animation: 'pulse 1.5s infinite' }} />
        </div>
        <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}} @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}`}</style>
      </div>
    );
  }

  if (!job) return null;

  const statusConfig = {
    completed: { color: '#10b981', bg: 'rgba(16,185,129,0.1)', border: 'rgba(16,185,129,0.3)', icon: <CheckCircle size={16} color="#10b981" /> },
    failed:    { color: '#ef4444', bg: 'rgba(239,68,68,0.1)',  border: 'rgba(239,68,68,0.3)',  icon: <XCircle size={16} color="#ef4444" /> },
    running:   { color: '#6366f1', bg: 'rgba(99,102,241,0.08)', border: 'rgba(99,102,241,0.2)', icon: <Loader2 size={16} color="#6366f1" style={{ animation: 'spin 1s linear infinite' }} /> },
    pending:   { color: '#f59e0b', bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.2)', icon: <Clock size={16} color="#f59e0b" /> },
    cancelled: { color: '#94a3b8', bg: 'rgba(148,163,184,0.08)', border: 'rgba(148,163,184,0.2)', icon: <XCircle size={16} color="#94a3b8" /> },
  };
  const cfg = statusConfig[job.status] || statusConfig.pending;
  const barColor = job.status === 'completed' ? '#10b981' : job.status === 'failed' ? '#ef4444' : '#6366f1';

  return (
    <div style={{ background: cfg.bg, borderRadius: 14, border: `1px solid ${cfg.border}`, padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {cfg.icon}
          <span style={{ fontSize: 13, fontWeight: 700, color: '#0f172a' }}>{job.job_name}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {job.estimated_completion_seconds && job.status === 'running' && (
            <span style={{ fontSize: 11, color: '#94a3b8' }}>~{Math.ceil(job.estimated_completion_seconds / 60)}m</span>
          )}
          <span style={{ fontSize: 11, fontWeight: 700, color: cfg.color, background: `${cfg.color}15`, padding: '2px 8px', borderRadius: 99, textTransform: 'capitalize' }}>
            {job.status}
          </span>
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ width: '100%', height: 6, background: 'rgba(0,0,0,0.08)', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{ width: `${job.progress_percent}%`, height: '100%', background: barColor, borderRadius: 99, transition: 'width 0.4s ease' }} />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 12, color: '#64748b' }}>{job.progress_message || (job.status === 'pending' ? 'Waiting to start...' : job.status === 'running' ? 'Processing...' : '')}</span>
        <span style={{ fontSize: 12, fontWeight: 700, color: cfg.color }}>{job.progress_percent}%</span>
      </div>

      {error && (
        <div style={{ background: 'rgba(239,68,68,0.08)', borderRadius: 8, padding: '8px 10px', fontSize: 12, color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}>
          {error}
        </div>
      )}

      {job.status === 'completed' && job.result && Object.keys(job.result).length > 0 && (
        <div style={{ background: 'rgba(16,185,129,0.08)', borderRadius: 8, padding: '8px 10px', fontSize: 12, color: '#059669', border: '1px solid rgba(16,185,129,0.2)' }}>
          <span style={{ fontWeight: 700 }}>Complete</span> — result saved successfully
        </div>
      )}

      <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}

export default JobProgress;
