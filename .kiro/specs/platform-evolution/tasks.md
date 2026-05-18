# Implementation Tasks — Platform Evolution

## Task List

- [x] 1. Sidebar Navigation Restructure
  - [x] 1.1 Replace flat NAV array in `frontend/components/AppShell.tsx` with `NAV_GROUPS` structure (Business Tools, Developer Tools, System)
  - [x] 1.2 Update sidebar render loop to iterate over groups, rendering section labels and items per group
  - [x] 1.3 Remove duplicate Settings entry and remove Generator, AI Agent, AI Playground entries from nav
  - [x] 1.4 Add `WorkspaceSwitcher` placeholder component above nav groups in sidebar header

- [x] 2. Rename AI Playground to AI Studio
  - [x] 2.1 Create `frontend/app/ai-studio/page.tsx` by copying and updating `frontend/app/ai-playground/page.tsx`
  - [x] 2.2 Create `frontend/app/ai-playground/page.tsx` redirect component pointing to `/ai-studio`
  - [x] 2.3 Update all sidebar nav references from `/ai-playground` to `/ai-studio` with label "AI Studio" and Sparkles icon
  - [x] 2.4 Update page title, browser tab title, and all in-page headings in the new AI Studio page

- [x] 3. AI Studio — Premium Three-Panel Layout
  - [x] 3.1 Redesign `frontend/app/ai-studio/page.tsx` with three-column grid: left prompt panel, centre preview iframe, right version history panel
  - [x] 3.2 Add multi-step generation progress indicator (Planning → Generating → Applying → Rendering → Complete) shown during AI calls
  - [x] 3.3 Add version history panel rendering a list of past AI changes with timestamp, label, and Restore button
  - [x] 3.4 Implement undo action that reverts the most recent AI change in local state
  - [x] 3.5 Add contextual prompt suggestions (min 5) that update based on selected business
  - [x] 3.6 Add diff card display showing field changed, before value, and after value for each AI response
  - [x] 3.7 Add business selector in top bar with conversation history preserved per business

- [x] 4. AI Memory Backend
  - [x] 4.1 Create `backend/app/models/ai_memory.py` with AIMemory SQLAlchemy model
  - [x] 4.2 Create `backend/migrations/versions/0011_ai_memory.py` Alembic migration
  - [x] 4.3 Create `backend/app/services/ai_memory_service.py` with get_context, save_context, append_example, inject_into_prompt methods
  - [x] 4.4 Create `backend/app/api/routes/ai_memory.py` with GET and POST `/ai/memory/{business_id}` endpoints
  - [x] 4.5 Register ai_memory router in `backend/app/api/router.py`
  - [x] 4.6 Add Brand Context panel to AI Studio left panel with editable fields (tone, audience, differentiators)

- [x] 5. AI Code Editor — Multi-File Tabs
  - [x] 5.1 Add tab bar above editor in `frontend/app/code-editor/page.tsx` supporting multiple open files
  - [x] 5.2 Add unsaved-changes dot indicator on tabs with dirty state tracking
  - [x] 5.3 Prompt save/reject confirmation when switching away from a file with unsaved AI changes

- [x] 6. AI Code Editor — Inline Cmd+K Action
  - [x] 6.1 Add keydown listener for Cmd/Ctrl+K in the editor textarea
  - [x] 6.2 Render floating prompt input anchored near cursor position when shortcut is triggered
  - [x] 6.3 Submit inline prompt to existing `/code-editor/ai-edit` endpoint and apply result

- [x] 7. AI Code Editor — Agent Plan Panel
  - [x] 7.1 Add Agent Plan slide-in panel component to code editor page
  - [x] 7.2 When an AI instruction is classified as multi-step, show plan steps with Approve/Cancel before execution
  - [x] 7.3 Add "Generate Tests" action button that sends selected function content to AI with test generation prompt

- [x] 8. RAG / Embedding Service — Backend
  - [x] 8.1 Create `backend/app/models/code_embedding.py` with CodeEmbedding model
  - [x] 8.2 Create `backend/migrations/versions/0012_code_embeddings.py` migration
  - [x] 8.3 Create `backend/app/services/embedding_service.py` with chunk_file, index_workspace, search methods using cosine similarity over stored vectors
  - [x] 8.4 Create `backend/app/api/routes/embeddings.py` with POST `/code-editor/search` and POST `/code-editor/index` endpoints
  - [x] 8.5 Register embeddings router in `backend/app/api/router.py`
  - [x] 8.6 Wire frontend code editor to call `/code-editor/search` before AI edit, prepending top-5 chunks to prompt context

- [x] 9. AI Ops Panel — Token and Latency Charts
  - [x] 9.1 Add `GET /ai/telemetry/tokens` endpoint returning per-provider token usage bucketed by hour for last 24h
  - [x] 9.2 Add `GET /ai/telemetry/latency` endpoint returning p50/p95/p99 latency per provider for last 24h
  - [x] 9.3 Add token usage chart section to `frontend/app/ops/page.tsx` using inline SVG bar chart (no external chart lib required)
  - [x] 9.4 Add latency percentile chart section using inline SVG line chart

- [x] 10. AI Ops Panel — Fallback History and Circuit Breaker Reset
  - [x] 10.1 Add `GET /ai/telemetry/fallbacks` endpoint returning last 50 fallback events from telemetry service
  - [x] 10.2 Add `POST /ai/telemetry/reset/{provider}` endpoint that resets circuit breaker state for a provider
  - [x] 10.3 Add fallback history log section to ops page
  - [x] 10.4 Add "Reset Circuit" button to each provider card in ops page, calling the reset endpoint

- [x] 11. AI Ops Panel — Live SSE Events and Routing Logic
  - [x] 11.1 Add `GET /ai/telemetry/stream` SSE endpoint streaming live telemetry events
  - [x] 11.2 Add `GET /ai/telemetry/routing` endpoint returning current provider priority order and circuit states
  - [x] 11.3 Add live events panel to ops page connecting to SSE stream
  - [x] 11.4 Add model routing logic panel showing provider order and fallback conditions

- [x] 12. Workspace and Project System — Backend
  - [x] 12.1 Create `backend/app/models/workspace.py` with Workspace, WorkspaceMember, Project models
  - [x] 12.2 Create `backend/migrations/versions/0009_workspaces_projects.py` migration
  - [x] 12.3 Create `backend/app/services/workspace_service.py` with CRUD, invite, role enforcement
  - [x] 12.4 Create `backend/app/api/routes/workspaces.py` with workspace and project CRUD endpoints
  - [x] 12.5 Register workspaces router in `backend/app/api/router.py`
  - [x] 12.6 Add env var management endpoints: GET/POST/DELETE `/projects/{id}/envvars`

- [x] 13. Workspace and Project System — Frontend
  - [x] 13.1 Create `frontend/components/WorkspaceSwitcher.tsx` dropdown component
  - [x] 13.2 Create `frontend/app/workspace/page.tsx` workspace overview page
  - [x] 13.3 Create `frontend/app/workspace/[slug]/project/[id]/page.tsx` project overview page
  - [x] 13.4 Wire WorkspaceSwitcher into AppShell sidebar header

- [x] 14. Deployment System — Backend
  - [x] 14.1 Create `backend/app/models/deployment.py` with Deployment and DeploymentCheck models
  - [x] 14.2 Create `backend/migrations/versions/0010_deployments.py` migration
  - [x] 14.3 Create `backend/app/services/deployment_service.py` with create_preview, promote_to_production, rollback, run_ai_checks, stream_build_log
  - [x] 14.4 Create `backend/app/api/routes/deployments.py` with all deployment endpoints including SSE build log
  - [x] 14.5 Register deployments router in `backend/app/api/router.py`

- [x] 15. Deployment System — Frontend
  - [x] 15.1 Create `frontend/app/deploy/[project_id]/page.tsx` with deployment history table, build log terminal, and AI checks checklist
  - [x] 15.2 Add rollback confirmation dialog component
  - [x] 15.3 Add env var editor component with masked value display

- [x] 16. Product Polish — Design Tokens and Global Styles
  - [x] 16.1 Add CSS custom property token system to `frontend/app/globals.css` (colours, typography scale, spacing, radii, shadows)
  - [x] 16.2 Create `frontend/components/SkeletonCard.tsx` reusable skeleton loader component
  - [x] 16.3 Create `frontend/components/ToastProvider.tsx` global toast notification system with useToast hook
  - [x] 16.4 Add ToastProvider to root layout in `frontend/app/layout.tsx`
  - [x] 16.5 Replace spinner-only loading states on Dashboard, Marketing, Analytics, and Support pages with skeleton loaders

- [x] 17. Product Polish — Empty States
  - [x] 17.1 Audit all list/data views for missing empty states (campaigns, SEO content, support conversations, products, jobs)
  - [x] 17.2 Add designed empty state (icon + headline + description + CTA) to each identified view

- [x] 18. Onboarding Flow
  - [x] 18.1 Add `onboarding_complete` boolean and `subscription_tier` string fields to User model via migration `0013_user_tier_onboarding.py`
  - [x] 18.2 Create `backend/app/services/onboarding_service.py` with step tracking and welcome email trigger
  - [x] 18.3 Create `backend/app/api/routes/onboarding.py` with GET `/onboarding/status` and POST `/onboarding/complete/{step}`
  - [x] 18.4 Create `frontend/components/OnboardingChecklist.tsx` floating checklist card
  - [x] 18.5 Render OnboardingChecklist on Dashboard page when `onboarding_complete = false`

- [ ] 19. Monetisation — Feature Gates
  - [x] 19.1 Add `check_feature_gate` method and `GatedFeature` enum to `backend/app/services/usage_limit_service.py`
  - [x] 19.2 Create `frontend/hooks/useFeatureGate.ts` hook calling `/usage/check-gate?feature=X`
  - [x] 19.3 Create `frontend/components/FeatureGateModal.tsx` upgrade prompt modal
  - [x] 19.4 Add tier badge to sidebar user footer showing current plan (Free / Pro / Enterprise)
  - [x] 19.5 Add `GET /usage/check-gate` endpoint to usage_limits router

- [ ] 20. Accessibility Foundations
  - [x] 20.1 Add `aria-label` to all icon-only buttons in AppShell, code editor, ops panel, and agent-live pages
  - [x] 20.2 Add visible focus ring styles to globals.css applied to all interactive elements
  - [x] 20.3 Ensure all form validation errors display inline text (not browser-native only) across auth, products, and marketing forms
  - [x] 20.4 Replace directional CSS properties (margin-left, padding-right) with logical properties in all new components
