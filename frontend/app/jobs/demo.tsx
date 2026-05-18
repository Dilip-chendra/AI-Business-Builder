'use client';

import { useState, useRef, useEffect } from 'react';
import JobProgress, { JobStatus } from '@/components/JobProgress';
import useJobStart from '@/hooks/useJobStart';

interface GenerateSEOProps {
  businessId: string;
}

/**
 * Example: Generate SEO Blog with Job Tracking
 * Demonstrates async job-based API usage
 */
export function GenerateSEOBlogWithJob({ businessId }: GenerateSEOProps) {
  const [topic, setTopic] = useState('');
  const [targetKeyword, setTargetKeyword] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobs, setJobs] = useState<string[]>([]);
  const { startSeoBlogJob, isLoading, error } = useJobStart({
    onSuccess: (response) => {
      setJobId(response.job_id);
      setJobs((prev) => [...prev, response.job_id]);
    },
  });

  const handleStartJob = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic || !targetKeyword) {
      alert('Please fill in all fields');
      return;
    }

    try {
      await startSeoBlogJob(businessId, topic, targetKeyword);
      setTopic('');
      setTargetKeyword('');
    } catch (err) {
      console.error('Failed to start job:', err);
    }
  };

  return (
    <div className="space-y-6 p-6 bg-white rounded-lg border">
      <div>
        <h3 className="text-lg font-semibold mb-4">Generate SEO Blog (Async)</h3>
        
        {/* Form */}
        <form onSubmit={handleStartJob} className="space-y-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Topic
            </label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g., Best practices for React hooks"
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Target Keyword
            </label>
            <input
              type="text"
              value={targetKeyword}
              onChange={(e) => setTargetKeyword(e.target.value)}
              placeholder="e.g., React hooks tutorial"
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 font-medium"
          >
            {isLoading ? 'Starting...' : 'Start SEO Blog Generation'}
          </button>
        </form>

        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm mb-4">
            {error}
          </div>
        )}
      </div>

      {/* Active Job Progress */}
      {jobId && (
        <div>
          <h4 className="font-medium mb-3">Current Job</h4>
          <JobProgress
            jobId={jobId}
            onComplete={(result) => {
              console.log('Job completed:', result);
              setJobId(null);
            }}
          />
        </div>
      )}

      {/* Job History */}
      {jobs.length > 0 && (
        <div>
          <h4 className="font-medium mb-3">Job History ({jobs.length})</h4>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {jobs.map((id) => (
              <div key={id} className="text-xs text-gray-600 p-2 bg-gray-50 rounded">
                Job ID: {id.substring(0, 8)}...
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Example: Generate Email Campaign with Job Tracking
 */
export function GenerateEmailCampaignWithJob({ businessId }: GenerateSEOProps) {
  const [campaignName, setCampaignName] = useState('');
  const [goal, setGoal] = useState('');
  const [recipientCount, setRecipientCount] = useState(0);
  const [jobId, setJobId] = useState<string | null>(null);
  const { startEmailCampaignJob, isLoading, error } = useJobStart();

  const handleStartJob = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!campaignName || !goal) {
      alert('Please fill in all fields');
      return;
    }

    try {
      const response = await startEmailCampaignJob(
        businessId,
        campaignName,
        goal,
        recipientCount
      );
      setJobId(response.job_id);
      setCampaignName('');
      setGoal('');
      setRecipientCount(0);
    } catch (err) {
      console.error('Failed to start job:', err);
    }
  };

  return (
    <div className="space-y-6 p-6 bg-white rounded-lg border">
      <div>
        <h3 className="text-lg font-semibold mb-4">Generate Email Campaign (Async)</h3>
        
        <form onSubmit={handleStartJob} className="space-y-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Campaign Name
            </label>
            <input
              type="text"
              value={campaignName}
              onChange={(e) => setCampaignName(e.target.value)}
              placeholder="e.g., Summer Sale Campaign"
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Campaign Goal
            </label>
            <textarea
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="Describe the goal of this campaign..."
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              rows={3}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Estimated Recipients
            </label>
            <input
              type="number"
              value={recipientCount}
              onChange={(e) => setRecipientCount(Number(e.target.value))}
              placeholder="0"
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 font-medium"
          >
            {isLoading ? 'Starting...' : 'Start Campaign Generation'}
          </button>
        </form>

        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm mb-4">
            {error}
          </div>
        )}
      </div>

      {jobId && (
        <div>
          <h4 className="font-medium mb-3">Current Job</h4>
          <JobProgress jobId={jobId} />
        </div>
      )}
    </div>
  );
}

/**
 * Demo page showing both job generation methods
 */
export default function JobDemoPage({ params }: { params: { businessId: string } }) {
  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-2">Background Jobs Demo</h1>
        <p className="text-gray-600 mb-8">
          Examples of using the async job system for long-running AI tasks
        </p>

        <div className="grid grid-cols-1 gap-8">
          <GenerateSEOBlogWithJob businessId={params.businessId} />
          <GenerateEmailCampaignWithJob businessId={params.businessId} />
        </div>

        {/* Documentation */}
        <div className="mt-12 p-6 bg-blue-50 border border-blue-200 rounded-lg">
          <h2 className="text-lg font-semibold text-blue-900 mb-4">How It Works</h2>
          <ul className="text-sm text-blue-800 space-y-2">
            <li>✅ Job is created and stored in database</li>
            <li>✅ Task is dispatched to Celery worker</li>
            <li>✅ Frontend polls /jobs/{'{jobId}'} for progress updates</li>
            <li>✅ Progress bar updates in real-time</li>
            <li>✅ Results are returned when job completes</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
