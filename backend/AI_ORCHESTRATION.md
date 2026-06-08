# AI Provider Orchestration - Smart Routing Guide

## Overview

The `SmartAIOrchestrator` intelligently routes AI requests to the best available provider based on:
- Task complexity (simple, medium, complex)
- Provider availability
- Rate limiting status
- Request timeouts

This system improves reliability and cost-efficiency by automatically selecting the right provider for each task.

---

## Architecture

### Provider Priority

**By Complexity:**

| Complexity | 1st Choice | 2nd Choice | 3rd Choice |
|----------|-----------|----------|----------|
| **SIMPLE** | Groq (fast, cheap) | Ollama (local) | HuggingFace |
| **MEDIUM** | Ollama (stable) | Groq (fallback) | HuggingFace |
| **COMPLEX** | Groq (best quality) | Ollama (stable) | HuggingFace |

### Complexity Estimation

```python
# Automatic based on prompt analysis:
- Length < 200 chars, no JSON → SIMPLE
- Length 200-500 chars, no reasoning → MEDIUM
- Length > 500 chars or reasoning required → COMPLEX
```

### Retry Strategy

```
Attempt 1
    ↓ (success)
Return result
    ↓ (failure)
Wait: initial_delay (1s)
    ↓
Attempt 2
    ↓ (failure)
Wait: initial_delay × multiplier (2s)
    ↓
Attempt 3
    ↓ (failure)
Try next provider
    ↓ (all providers fail)
Raise AIProviderError
```

**Backoff Configuration:**
- Initial delay: 1 second
- Multiplier: 2x
- Max delay: 60 seconds
- Max retries per provider: 3

---

## Usage

### Basic Usage

```python
from app.services.ai_orchestrator import generate_text_smart, generate_json_smart

# Auto-select provider
text = await generate_text_smart("Write a blog post about...")

# Auto-parse JSON
data = await generate_json_smart("Generate SEO metadata in JSON...")
```

### Force Specific Provider

```python
from app.services.ai_orchestrator import ProviderChoice

# Always use Groq
text = await generate_text_smart(
    prompt="...",
    prefer_provider=ProviderChoice.GROQ
)

# Always use Ollama
text = await generate_text_smart(
    prompt="...",
    prefer_provider=ProviderChoice.OLLAMA
)
```

### Health Check

```python
from app.services.ai_orchestrator import health_check

status = await health_check()
print(status)
# {
#   "groq": True,
#   "huggingface": False,
#   "ollama": True,
#   "any_available": True,
#   "recommended_provider": "groq"
# }
```

---

## Integration with Existing Services

### Marketing Service

```python
from app.services.marketing_service import MarketingService
from app.services.ai_orchestrator import generate_json_smart, ProviderChoice

# Automatically uses smart orchestrator internally
content = await marketing_svc.generate_seo_blog(
    business_id=business_id,
    topic="...",
    target_keyword="..."
)
```

### Celery Tasks

```python
@celery_app.task(bind=True, max_retries=3)
def process_code_edit_job_task(self, job_id: str, payload: dict):
    async def _run():
        from app.services.ai_orchestrator import generate_text_smart
        
        # Smart provider selection + exponential backoff
        result = await generate_text_smart(
            prompt=payload.get("instruction"),
            prefer_provider=ProviderChoice.AUTO
        )
        return result
    
    return _run_async(_run())
```

---

## Retry-After Header Handling

When a provider returns HTTP 429 (rate limited) with a `Retry-After` header:

```
1. Extract Retry-After value from error message
2. Sleep for specified seconds
3. Retry the same provider
4. If retries exhausted, try next provider
```

Example:
```
Groq returns: HTTP 429 "Retry-After: 30s"
    ↓
Sleep 30 seconds
    ↓
Retry Groq
    ↓
On success, return result
On failure, try Ollama
```

---

## Provider-Specific Behavior

### Groq

- **Speed**: ⚡⚡⚡ Fastest
- **Cost**: 💰 Free tier (with API key)
- **Complexity**: Best for complex reasoning
- **Limits**: Rate limited (handles exponential backoff)
- **When**: Primary choice for complex tasks

### Ollama (Local)

- **Speed**: ⚡ Fast (local)
- **Cost**: 💰 Free (runs locally)
- **Complexity**: Good for medium tasks
- **Limits**: No rate limiting (stable)
- **When**: Recommended for production stability

### HuggingFace

- **Speed**: ⚡ Variable (model cold-start)
- **Cost**: 💰 Free tier (limited)
- **Complexity**: Works for all
- **Limits**: Model loading delays
- **When**: Last resort fallback

---

## Configuration

### Settings (Environment Variables)

```env
# All existing settings still work
GROQ_API_KEY=your-key
HF_API_KEY=your-key
OLLAMA_BASE_URL=http://localhost:11434

# Orchestrator uses these internally
# No additional config needed!
```

---

## Monitoring & Debugging

### Check Provider Status

```bash
curl http://localhost:8000/api/v1/ai/health
# {
#   "groq": true,
#   "huggingface": false,
#   "ollama": true,
#   "any_available": true
# }
```

### View Retry Attempts

Enable debug logging in Docker/systemd:

```python
import logging
logging.getLogger("app.services.ai_orchestrator").setLevel(logging.DEBUG)
```

Logs will show:
```
DEBUG: AI request attempt  provider=groq  attempt=1/3
DEBUG: Provider failed, retrying  provider=groq  delay=1.0s
DEBUG: AI request attempt  provider=groq  attempt=2/3
INFO: AI generation succeeded  provider=groq  attempts=2
```

---

## Error Scenarios

### Scenario 1: Groq Rate Limited

```
Request → Groq (attempt 1)
    ↓ (HTTP 429, Retry-After: 30)
Wait 30s
    ↓
Groq (attempt 2) → Success ✓
```

### Scenario 2: Groq Down, Ollama Works

```
Request → Groq (attempt 1-3, all fail)
    ↓
Ollama (attempt 1) → Success ✓
```

### Scenario 3: All Providers Fail

```
Request → Groq (attempts 1-3, all fail)
       → Ollama (attempts 1-3, all fail)
       → HuggingFace (attempts 1-3, all fail)
    ↓
Raise AIProviderError with details
```

---

## Performance Characteristics

### Latency (Avg)

| Provider | Simple | Medium | Complex |
|----------|--------|--------|---------|
| Groq | 500ms | 2s | 4s |
| Ollama | 1s | 3s | 6s |
| HuggingFace | 3s | 8s | 15s |

### With Retry (Worst Case)

```
Simple task:   500ms + (1s + 2s + 4s) = 7.5s
Medium task:   2s + (1s + 2s + 4s) = 9s
Complex task:  4s + (1s + 2s + 4s) = 11s
```

---

## Best Practices

1. **Use ProviderChoice.AUTO** (default)
   - Orchestrator chooses optimally
   - Only override for specific reasons

2. **Handle AIProviderError**
   ```python
   try:
       result = await generate_text_smart(prompt)
   except AIProviderError as e:
       logger.error("All providers failed: %s", e)
       # Return cached result or user-friendly error
   ```

3. **Monitor Provider Health**
   ```python
   health = await health_check()
   if not health["any_available"]:
       # Alert ops team
       send_alert("All AI providers down")
   ```

4. **Set Realistic Job ETAs**
   - Simple: 10s estimated
   - Medium: 30s estimated
   - Complex: 60s estimated

5. **Log Thoroughly**
   - Orchestrator logs all provider attempts
   - Use for debugging and optimization

---

## Future Enhancements

- [ ] Provider cost tracking (optimize for cost vs speed)
- [ ] Machine learning-based complexity estimation
- [ ] Provider performance metrics (historical success rate)
- [ ] Concurrent provider requests (race best N providers)
- [ ] Adaptive backoff based on historical patterns
- [ ] Provider health scoring system

---
