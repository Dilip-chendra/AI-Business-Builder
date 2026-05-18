# Background Job System Documentation

## Overview

The Background Job System enables asynchronous processing of long-running AI tasks (SEO blog generation, email campaign creation, code editing, etc.) without blocking the HTTP request/response cycle.

**Architecture:**
- **Job Model**: Tracks job state, progress, and results in PostgreSQL
- **Celery Workers**: Process tasks asynchronously using Redis broker
- **API Endpoints**: Manage job creation, tracking, and cancellation
- **Frontend Components**: Real-time progress UI with polling

---

## Key Features

✅ **Real-time Progress Tracking**: Poll `/api/v1/jobs/{job_id}` for live updates
✅ **Automatic Retries**: Failed jobs retry with exponential backoff
✅ **Error Handling**: Detailed error messages and tracebacks stored
✅ **Progress Granularity**: Track percent, message, start/end times
✅ **Job Cancellation**: Cancel pending or running jobs
✅ **User Isolation**: Jobs linked to user_id, business_id for multi-tenancy
✅ **Scalable**: Celery + Redis scales to thousands of concurrent jobs

---

## Database Schema

### Jobs Table

```sql
CREATE TABLE jobs (
  id UUID PRIMARY KEY,
  user_id UUID FOREIGN KEY (users.id),
  business_id UUID FOREIGN KEY (businesses.id),
  job_type VARCHAR(40),           -- marketing_campaign, seo_blog, code_edit, etc.
  status VARCHAR(40),             -- pending, running, completed, failed, cancelled
  celery_task_id VARCHAR(255),    -- Celery task ID for tracking
  job_name VARCHAR(255),          -- Human-readable job name
  job_description VARCHAR(500),   -- Optional description
  payload JSON,                   -- Input parameters
  progress_percent INT,           -- 0-100
  progress_message VARCHAR(500),  -- e.g., "Generating content..."
  result JSON,                    -- Output/result data
  error_message TEXT,             -- Error details if failed
  error_traceback TEXT,           -- Full traceback if failed
  retry_count INT,                -- Number of retries
  max_retries INT,                -- Max retry attempts
  next_retry_at TIMESTAMP,        -- When to retry (exponential backoff)
  started_at TIMESTAMP,           -- When job started running
  completed_at TIMESTAMP,         -- When job completed
  estimated_completion_seconds INT, -- ETA
  metadata JSON,                  -- Custom metadata
  created_at TIMESTAMP,           -- Created timestamp
  updated_at TIMESTAMP            -- Last update timestamp
);

-- Indexes for fast lookups
CREATE INDEX idx_jobs_user_id ON jobs(user_id);
CREATE INDEX idx_jobs_business_id ON jobs(business_id);
CREATE INDEX idx_jobs_job_type ON jobs(job_type);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_celery_task_id ON jobs(celery_task_id);
```

---

## Job Types

```python
class JobType(str, enum.Enum):
    MARKETING_CAMPAIGN = "marketing_campaign"   # Email, social, ads
    SEO_BLOG = "seo_blog"                      # Blog post generation
    CODE_EDIT = "code_edit"                    # AI code editing
    AGENT_PIPELINE = "agent_pipeline"          # Multi-agent optimization
    BUSINESS_GENERATION = "business_generation"  # Full business creation
```

---

## Job Lifecycle

```
PENDING (waiting to run)
    ↓
RUNNING (Celery worker processing)
    ↓
COMPLETED (success) or FAILED (error)
    ↓
    If FAILED and retries < max:
        → PENDING (retry with exponential backoff)
    Otherwise:
        → FAILED (final failure)

User can CANCEL jobs in PENDING or RUNNING state.
```

---

## API Endpoints

### 1. Create Job

**POST** `/api/v1/jobs/`

Creates a job record (doesn't dispatch task; caller must dispatch separately)

```bash
curl -X POST http://localhost:8000/api/v1/jobs/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "seo_blog",
    "job_name": "Generate SEO Blog",
    "business_id": "123e4567-e89b-12d3-a456-426614174000",
    "payload": {
      "topic": "Best React Hooks",
      "target_keyword": "react hooks tutorial"
    },
    "estimated_completion_seconds": 120
  }'
```

Response:
```json
{
  "id": "job-id",
  "job_type": "seo_blog",
  "status": "pending",
  "progress_percent": 0,
  "created_at": "2026-05-06T10:00:00"
}
```

### 2. Get Job Status

**GET** `/api/v1/jobs/{job_id}`

Retrieve current job status and progress

```bash
curl http://localhost:8000/api/v1/jobs/job-123 \
  -H "Authorization: Bearer $TOKEN"
```

Response:
```json
{
  "id": "job-123",
  "job_type": "seo_blog",
  "status": "running",
  "job_name": "Generate SEO Blog",
  "progress_percent": 45,
  "progress_message": "Generating content...",
  "result": {},
  "error_message": null,
  "estimated_completion_seconds": 120,
  "started_at": "2026-05-06T10:00:05"
}
```

### 3. List User Jobs

**GET** `/api/v1/jobs/?job_type=seo_blog&status=running&limit=50`

List all jobs for current user with optional filtering

```bash
curl "http://localhost:8000/api/v1/jobs/?job_type=seo_blog&status=running" \
  -H "Authorization: Bearer $TOKEN"
```

Response:
```json
{
  "total": 3,
  "jobs": [
    { "id": "job-1", "status": "running", ... },
    { "id": "job-2", "status": "pending", ... }
  ]
}
```

### 4. Cancel Job

**POST** `/api/v1/jobs/{job_id}/cancel`

Cancel a pending or running job

```bash
curl -X POST http://localhost:8000/api/v1/jobs/job-123/cancel \
  -H "Authorization: Bearer $TOKEN"
```

### 5. Retry Failed Job

**POST** `/api/v1/jobs/{job_id}/retry`

Retry a failed job (resets to pending)

```bash
curl -X POST http://localhost:8000/api/v1/jobs/job-123/retry \
  -H "Authorization: Bearer $TOKEN"
```

---

## Backend Integration (Celery Tasks)

### Example: SEO Blog Generation Task

```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_seo_blog_job_task(self, job_id: str, business_id: str, payload: dict):
    """Generate SEO blog and track progress via Job model."""
    async def _run():
        from app.services.job_service import JobService
        from app.services.marketing_service import MarketingService

        async with _get_db_session() as db:
            job_svc = JobService(db)
            
            # Mark as running
            job = await job_svc.set_running(job_id, celery_task_id=self.request.id)
            
            try:
                # Update progress
                await job_svc.update_progress(job_id, 25, "Fetching context...")
                
                # Do work
                content = await MarketingService(db).generate_seo_blog(...)
                
                # Mark complete
                await job_svc.mark_completed(job_id, result={
                    "content_id": str(content.id),
                    "title": content.title
                })
                
                return str(content.id)
                
            except Exception as exc:
                # Mark failed with retry option
                await job_svc.mark_failed(
                    job_id,
                    error_message=str(exc),
                    error_traceback=traceback.format_exc(),
                    should_retry=True  # Will retry if < max_retries
                )
                raise
    
    try:
        return _run_async(_run())
    except Exception as exc:
        raise self.retry(exc=exc)
```

### Dispatching Tasks

From API routes, dispatch task to Celery:

```python
from app.worker import celery_app

# Create job record
job = await job_svc.create_job(
    job_type=JobType.SEO_BLOG,
    job_name="Generate SEO Blog",
    user_id=current_user.id,
    business_id=business_id,
    payload={"topic": "...", "target_keyword": "..."}
)

# Dispatch to Celery
task = celery_app.send_task(
    "app.tasks.generate_seo_blog_job_task",
    args=[str(job.id), str(business_id)],
    kwargs={"payload": job.payload},
    task_id=f"seo-blog-{job.id}"
)
```

---

## Frontend Integration

### Using JobProgress Component

```typescript
'use client';

import JobProgress from '@/components/JobProgress';

export function MyComponent({ jobId }: { jobId: string }) {
  return (
    <JobProgress
      jobId={jobId}
      refreshInterval={2000}
      onComplete={(result) => {
        console.log('Job completed with result:', result);
      }}
      onError={(error) => {
        console.error('Job failed:', error);
      }}
    />
  );
}
```

### Using useJobStart Hook

```typescript
import useJobStart from '@/hooks/useJobStart';

export function MyForm() {
  const { startSeoBlogJob, isLoading, error } = useJobStart();
  const [jobId, setJobId] = useState<string | null>(null);

  const handleSubmit = async (topic: string, keyword: string) => {
    const response = await startSeoBlogJob(businessId, topic, keyword);
    setJobId(response.job_id);
  };

  return (
    <>
      <button onClick={() => handleSubmit('...', '...')}>
        {isLoading ? 'Starting...' : 'Generate'}
      </button>
      {jobId && <JobProgress jobId={jobId} />}
    </>
  );
}
```

---

## Running the System

### 1. Start Redis

```bash
# Using Docker
docker run -d -p 6379:6379 redis:7-alpine

# Or brew (macOS)
brew services start redis
```

### 2. Apply Database Migration

```bash
cd backend
alembic upgrade head
```

### 3. Start Celery Worker

```bash
cd backend
celery -A app.worker worker --loglevel=info
```

### 4. Start Celery Beat Scheduler (optional)

```bash
cd backend
celery -A app.worker beat --loglevel=info
```

### 5. Start Backend API

```bash
cd backend
python -m uvicorn app.main:app --reload
```

### 6. Start Frontend

```bash
cd frontend
npm run dev
```

---

## Monitoring & Debugging

### Check Redis Connection

```bash
redis-cli ping
# Response: PONG
```

### View Celery Tasks

```bash
# Connect to worker logs
celery -A app.worker inspect active

# Get task stats
celery -A app.worker inspect stats
```

### Query Jobs Database

```python
from sqlalchemy import select
from app.models.job import Job, JobStatus

# Get all running jobs
async with async_session() as db:
    result = await db.execute(
        select(Job).where(Job.status == JobStatus.RUNNING)
    )
    running_jobs = result.scalars().all()
    for job in running_jobs:
        print(f"{job.id}: {job.progress_percent}% - {job.progress_message}")
```

---

## Best Practices

1. **Set Realistic ETAs**: Estimate completion time based on historical data
2. **Granular Progress Updates**: Update every 5-10%, not just start/end
3. **Meaningful Messages**: Help users understand what's happening
4. **Store Results Fully**: Include all relevant data in `result` JSON
5. **Error Context**: Always include traceback for debugging
6. **Retry Strategy**: Use exponential backoff, max 3-5 retries
7. **User Feedback**: Show progress UI even during polling delays
8. **Cleanup**: Implement a job cleanup task to archive old completed jobs

---

## Troubleshooting

### Task Not Running

```python
# Check if task is registered
celery -A app.worker inspect registered

# Ensure task name matches: "app.tasks.generate_seo_blog_job_task"
```

### Jobs Stuck in RUNNING

```python
# Manually cancel or mark as failed
from app.services.job_service import JobService

job_svc = JobService(db)
await job_svc.mark_failed(
    job_id,
    error_message="Stale job, manually cancelled",
    should_retry=False
)
```

### High Memory Usage

- Reduce number of Celery workers (default: 4)
- Lower job timeout and retry settings
- Implement job result cleanup (archive after 30 days)

---

## Future Enhancements

- [ ] Job result versioning (store all versions)
- [ ] Job dependencies (task A must complete before B)
- [ ] Priority queue (high-priority jobs run first)
- [ ] Scheduled jobs (run at specific time)
- [ ] Webhooks (notify when job completes)
- [ ] Admin dashboard (see all jobs across all users)
- [ ] Job templates (pre-configured job types)
- [ ] Batch jobs (process multiple jobs atomically)

---
