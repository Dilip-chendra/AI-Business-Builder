# Requirements Document

## Introduction

This document defines the requirements for evolving the existing AI-powered SaaS platform into a world-class AI-native operating system. The platform currently serves two distinct user personas — **Founders** (business builders using AI to generate, market, and operate businesses) and **Developers** (engineers using AI to write, review, and deploy code). The evolution addresses ten strategic areas: product positioning, navigation architecture, feature naming, AI Studio experience, AI Code Editor maturity, AI Ops observability, workspace/project system, deployment system, product polish, and strategic roadmap.

The goal is to achieve parity in quality and experience with best-in-class tools: Cursor, Replit, Lovable, Vercel, Linear, Bolt.new, Notion AI, Retool, and Superhuman.

---

## Glossary

- **Platform**: The full AI-native operating system being built, encompassing both the Business Layer and Developer Layer.
- **Business Layer**: The set of tools serving Founders — Dashboard, AI Studio, Marketing Engine, Analytics, Products, Support, SEO, Campaign generation, and Business Automation.
- **Developer Layer**: The set of tools serving Developers — AI Code Editor, AI Orchestration, AI Telemetry, Provider Fallback, Diff/Apply/Reject workflow, Streaming edits, Source-level editing, Operational Tracing, and Provider Analytics.
- **Founder**: A user persona focused on building, launching, and growing AI-powered businesses without writing code.
- **Developer**: A user persona focused on writing, reviewing, and deploying code using AI assistance.
- **AI Studio**: The renamed and evolved version of the current "AI Playground" — a premium visual workspace for Founders to generate, edit, and deploy business assets using AI.
- **AI Code Editor**: The evolved developer IDE with multi-file editing, repository awareness, semantic code graphing, and autonomous agent capabilities.
- **AI Ops Panel**: The evolved observability and operations dashboard for monitoring AI provider health, token usage, latency, tracing, and agent execution.
- **Workspace**: A top-level container grouping one or more Projects, with shared team membership, environment configuration, and AI memory.
- **Project**: A named unit within a Workspace representing a single business or codebase, with its own deployment targets, environment variables, and version history.
- **Sidebar**: The primary navigation component rendered on all authenticated pages.
- **AppShell**: The root layout component wrapping all authenticated pages, containing the Sidebar and main content area.
- **SSE**: Server-Sent Events — the streaming protocol used for real-time AI output delivery.
- **Provider**: An AI inference backend (Groq, HuggingFace, Ollama) managed by the orchestration layer.
- **Circuit Breaker**: A fault-tolerance pattern that stops routing requests to a failing Provider until it recovers.
- **Diff/Apply/Reject**: The three-step workflow for reviewing AI-generated code changes before committing them.
- **RAG**: Retrieval-Augmented Generation — a technique for grounding AI responses in indexed codebase content.
- **Embedding**: A vector representation of a code chunk used for semantic search in RAG pipelines.
- **Agent**: An autonomous AI process that plans and executes multi-step tasks using tools.
- **Deployment Target**: A named environment (preview, staging, production) to which a Project can be deployed.
- **Token**: A unit of AI model input/output used for billing and quota tracking.

---

## Requirements

---

### Requirement 1: Sidebar Navigation Restructure

**User Story:** As a Founder or Developer, I want the sidebar to clearly separate business tools from developer tools, so that I can immediately find the tools relevant to my workflow without scanning an undifferentiated list.

#### Acceptance Criteria

1. THE Sidebar SHALL organise navigation items into exactly three labelled groups: **Business Tools**, **Developer Tools**, and **System**.
2. THE Sidebar SHALL render the Business Tools group containing: Dashboard, AI Studio, Marketing Engine, Products, Analytics, Support.
3. THE Sidebar SHALL render the Developer Tools group containing: AI Code Editor, Agent Live, AI Ops.
4. THE Sidebar SHALL render the System group containing: Settings, and any future administrative items.
5. WHEN a navigation item is active, THE Sidebar SHALL highlight it with a distinct visual indicator (background fill and accent dot) that is visually distinguishable from inactive items.
6. THE Sidebar SHALL display a section label above each group in uppercase, low-contrast text to create visual hierarchy without competing with item labels.
7. WHERE the viewport width is below 1024px, THE Sidebar SHALL collapse into a slide-over drawer triggered by a hamburger button in the mobile top bar.
8. THE Sidebar SHALL display each navigation item with a unique icon, a text label, and sufficient touch target size (minimum 40px height) for accessibility.
9. THE AppShell SHALL persist the Sidebar's collapsed/expanded state across page navigations within the same session.

---

### Requirement 2: Rename "AI Playground" to "AI Studio"

**User Story:** As a Founder, I want the business creation workspace to have a name that clearly communicates its purpose as a premium creative environment, so that I am not confused about whether it is a coding tool or a business-building tool.

#### Acceptance Criteria

1. THE Platform SHALL rename the route `/ai-playground` to `/ai-studio` and redirect any existing `/ai-playground` links to `/ai-studio`.
2. THE Sidebar SHALL display the item label "AI Studio" with a visual icon that communicates creation and generation (not code or terminal).
3. THE AI_Studio page title, browser tab title, and all in-page headings SHALL use the name "AI Studio".
4. THE Platform SHALL remove all occurrences of the string "AI Playground" from user-facing UI text, replacing them with "AI Studio".
5. WHEN a user navigates to `/ai-playground`, THE Platform SHALL redirect them to `/ai-studio` with HTTP 301 status.
6. THE AI_Studio SHALL display a subtitle that communicates its purpose: generating, editing, and deploying business assets using AI.

---

### Requirement 3: AI Studio — Premium Generation Experience

**User Story:** As a Founder, I want the AI Studio to provide a world-class multi-step generation workflow with live preview, version history, and conversational editing, so that I can build and iterate on business assets as fluidly as I would in Figma or Notion AI.

#### Acceptance Criteria

1. THE AI_Studio SHALL present a three-panel layout: a left prompt/context panel, a centre live preview panel, and a right generation history/version panel.
2. WHEN a Founder submits a generation prompt, THE AI_Studio SHALL display a multi-step progress indicator showing each stage of the generation pipeline (e.g., "Planning", "Generating content", "Applying changes", "Rendering preview").
3. WHEN generation completes, THE AI_Studio SHALL automatically refresh the live preview panel without requiring a manual page reload.
4. THE AI_Studio SHALL maintain a versioned history of all AI-generated changes, displaying each version with a timestamp, a short label derived from the instruction, and a one-click restore action.
5. WHEN a Founder clicks "Restore" on a version, THE AI_Studio SHALL revert the business asset to that version's state and refresh the preview.
6. THE AI_Studio SHALL support conversational editing: WHEN a Founder sends a follow-up instruction referencing a previous change, THE AI_Studio SHALL include the prior conversation context in the AI request.
7. THE AI_Studio SHALL display a diff card for each AI response, showing the field changed, the before value, and the after value.
8. THE AI_Studio SHALL provide a set of at least five contextual prompt suggestions that update based on the currently selected business and the most recent change.
9. WHEN no business is selected, THE AI_Studio SHALL display an empty state with a clear call-to-action to select or create a business.
10. THE AI_Studio SHALL support an undo action that reverts the most recent AI change without requiring navigation to the version history panel.
11. WHERE a Founder has multiple businesses, THE AI_Studio SHALL allow switching between businesses via a selector in the top bar, preserving the conversation history per business.
12. THE AI_Studio SHALL display a "Deploy" action that navigates the Founder to the Deployment System for the currently selected business.

---

### Requirement 4: AI Studio — AI Memory and Context System

**User Story:** As a Founder, I want the AI Studio to remember my brand preferences, tone of voice, and previous decisions, so that AI-generated content is consistent with my brand without me having to repeat context in every prompt.

#### Acceptance Criteria

1. THE AI_Studio SHALL maintain a per-business AI memory store containing: brand name, tone of voice, target audience, key differentiators, and previously approved content samples.
2. WHEN a Founder submits a generation prompt, THE AI_Studio SHALL automatically inject the relevant AI memory context into the AI request payload.
3. THE AI_Studio SHALL display a "Brand Context" panel where Founders can view and edit the stored AI memory for the selected business.
4. WHEN a Founder approves an AI-generated change, THE AI_Studio SHALL offer to save the approved content as a positive example in the AI memory store.
5. THE AI_Studio SHALL persist AI memory in the backend database, associated with the business ID and user ID.
6. IF the AI memory store for a business is empty, THEN THE AI_Studio SHALL prompt the Founder to complete a brand setup wizard before their first generation.

---

### Requirement 5: Advanced AI Code Editor

**User Story:** As a Developer, I want the AI Code Editor to function as a serious AI-native IDE with multi-file editing, repository awareness, and autonomous refactoring capabilities, so that I can use it as my primary development environment rather than a supplementary tool.

#### Acceptance Criteria

1. THE AI_Code_Editor SHALL display a file tree panel listing all files in the current Project's workspace, supporting expand/collapse of directories.
2. THE AI_Code_Editor SHALL allow a Developer to open multiple files simultaneously, displayed as tabs in the editor panel.
3. WHEN a Developer issues an AI instruction that spans multiple files, THE AI_Code_Editor SHALL apply changes to all affected files and display a multi-file diff view.
4. THE AI_Code_Editor SHALL maintain a per-file version history, allowing a Developer to revert any file to any previous AI-generated or manually saved version.
5. THE AI_Code_Editor SHALL support streaming AI edits via SSE, displaying tokens as they arrive in the editor panel with a visual "AI typing" indicator.
6. THE AI_Code_Editor SHALL provide an inline AI action triggered by a keyboard shortcut (Cmd/Ctrl+K) that opens a prompt input anchored to the current cursor position.
7. THE AI_Code_Editor SHALL index the codebase using Embeddings and RAG, enabling the AI to answer questions about the full codebase without the Developer manually pasting context.
8. WHEN a Developer asks a question about the codebase, THE AI_Code_Editor SHALL retrieve the top-N relevant code chunks via semantic search and include them in the AI request context.
9. THE AI_Code_Editor SHALL display an "Agent Plan" panel showing the steps an autonomous agent will take before executing a multi-step refactor, requiring explicit Developer approval before execution.
10. THE AI_Code_Editor SHALL generate unit tests for a selected function or file when the Developer triggers the "Generate Tests" action.
11. THE AI_Code_Editor SHALL display an AI code review summary when a Developer saves a file, highlighting potential bugs, style violations, and improvement suggestions.
12. WHEN a Developer applies AI changes, THE AI_Code_Editor SHALL record the instruction, the diff, and the timestamp in a persistent AI commit history accessible from the version panel.
13. THE AI_Code_Editor SHALL support a sandbox preview mode that renders HTML/CSS files in an iframe within the editor, updating on save.
14. IF a file has unsaved AI changes, THEN THE AI_Code_Editor SHALL display a visual indicator (dot on the tab) and prompt the Developer to save or reject before switching files.

---

### Requirement 6: AI Ops / Observability Panel

**User Story:** As a Developer or platform operator, I want a premium AI Ops panel that provides deep visibility into provider health, token usage, latency, tracing, and agent execution, so that I can diagnose failures, optimise costs, and ensure reliability.

#### Acceptance Criteria

1. THE AI_Ops_Panel SHALL display a real-time system health banner showing overall status (Healthy / Degraded / Failing), the number of available providers, total requests, fallback rate, and uptime.
2. THE AI_Ops_Panel SHALL render a provider card for each configured AI Provider (Groq, HuggingFace, Ollama), showing: success rate, average latency, circuit breaker state, provider score, total calls, failures, timeouts, and rate limits.
3. THE AI_Ops_Panel SHALL auto-refresh provider data every 7 seconds when the auto-refresh toggle is enabled.
4. THE AI_Ops_Panel SHALL display a recent failures log showing: provider name, error type, error message, latency, timestamp, and a prompt preview for each failure.
5. THE AI_Ops_Panel SHALL display a token usage chart showing cumulative token consumption per Provider over the last 24 hours, broken down by input and output tokens.
6. THE AI_Ops_Panel SHALL display a latency percentile chart (p50, p95, p99) per Provider over the last 24 hours.
7. THE AI_Ops_Panel SHALL display an agent execution graph visualising the steps, tool calls, and outcomes of the most recent Agent run.
8. THE AI_Ops_Panel SHALL display a fallback history log showing each fallback event: the primary provider that failed, the fallback provider used, the reason, and the timestamp.
9. THE AI_Ops_Panel SHALL display a live stream events panel showing real-time SSE events from active Agent runs, with event type, payload preview, and timestamp.
10. THE AI_Ops_Panel SHALL display a model routing logic panel showing the current provider priority order and the conditions under which each fallback is triggered.
11. WHEN a circuit breaker transitions to the "open" state, THE AI_Ops_Panel SHALL display a prominent alert banner identifying the affected Provider and the estimated recovery time.
12. THE AI_Ops_Panel SHALL allow a Developer to manually reset a circuit breaker for a specific Provider via a "Reset Circuit" action.

---

### Requirement 7: Workspace and Project System

**User Story:** As a Founder or Developer, I want a multi-project workspace architecture with team collaboration, environment management, and per-project AI memory, so that I can manage multiple businesses or codebases from a single account without context bleed between projects.

#### Acceptance Criteria

1. THE Platform SHALL support a Workspace entity that contains one or more Projects, with a unique name, slug, and owner user ID.
2. THE Platform SHALL support a Project entity within a Workspace, with a unique name, type (business or codebase), creation timestamp, and associated Deployment Targets.
3. THE AppShell SHALL display a Workspace switcher in the sidebar header, allowing a user to switch between their Workspaces without logging out.
4. WHEN a user switches Workspace, THE Platform SHALL update all data views (businesses, projects, analytics) to reflect the selected Workspace's data.
5. THE Platform SHALL support inviting team members to a Workspace by email, assigning them one of three roles: Owner, Editor, or Viewer.
6. WHEN a team member with Viewer role attempts a write action (create, update, delete), THE Platform SHALL return a 403 Forbidden response and display an in-app permission error.
7. THE Platform SHALL support per-Project environment management, allowing a user to define named environments (development, staging, production) with isolated environment variable sets.
8. THE Platform SHALL support Project templates, allowing a user to create a new Project pre-populated with a selected template's structure, AI memory, and initial content.
9. THE Platform SHALL maintain per-Project AI memory, ensuring that AI context from one Project does not influence AI responses in another Project.
10. THE Platform SHALL display a Project overview page showing: project name, type, last modified, active deployments, team members, and quick-action links.

---

### Requirement 8: Deployment System

**User Story:** As a Founder or Developer, I want a deployment system with preview deploys, production deploys, rollback, and AI-assisted deployment checks, so that I can ship changes confidently and recover quickly from failures.

#### Acceptance Criteria

1. THE Deployment_System SHALL support creating a preview deployment for any Project, generating a unique preview URL accessible without authentication.
2. THE Deployment_System SHALL support promoting a preview deployment to production, replacing the current production deployment.
3. THE Deployment_System SHALL maintain a deployment history for each Project, showing: deployment ID, environment, status (pending, building, live, failed, rolled back), timestamp, and the user who triggered it.
4. WHEN a deployment fails, THE Deployment_System SHALL display the build log and a clear error message identifying the failure reason.
5. THE Deployment_System SHALL support one-click rollback to any previous successful deployment in the deployment history.
6. WHEN a rollback is initiated, THE Deployment_System SHALL display a confirmation dialog showing the target deployment's timestamp and status before executing.
7. THE Deployment_System SHALL support per-environment environment variable management, allowing a user to set, update, and delete key-value pairs without exposing secret values in the UI after initial entry.
8. THE Deployment_System SHALL run AI-assisted pre-deployment checks before each production deployment, analysing the diff for: breaking API changes, missing environment variables, and security anti-patterns, and displaying a checklist of findings.
9. THE Deployment_System SHALL display deployment analytics showing: deployment frequency, average build time, rollback rate, and uptime per environment.
10. THE Deployment_System SHALL support connecting a custom domain to a production deployment, with DNS configuration instructions and SSL certificate status.
11. WHEN a deployment is in progress, THE Deployment_System SHALL display a real-time build log streamed via SSE.

---

### Requirement 9: Product Polish — UI Consistency System

**User Story:** As a user of the Platform, I want a visually consistent, premium interface with coherent typography, spacing, colour, animation, and empty states, so that the platform feels enterprise-grade and trustworthy rather than a collection of disconnected pages.

#### Acceptance Criteria

1. THE Platform SHALL apply a single, documented design token system for colours, typography, spacing, border radii, and shadows, used consistently across all pages and components.
2. THE Platform SHALL use a consistent typographic scale: page titles at 24–28px/800 weight, section headings at 16–18px/700 weight, body text at 13–14px/400 weight, and labels at 11–12px/600 weight uppercase.
3. THE Platform SHALL display a non-empty, visually designed empty state for every list or data view that can return zero results, including an icon, a headline, a description, and a primary call-to-action.
4. THE Platform SHALL display a skeleton loading state (animated placeholder) for every data-fetching component while data is loading, replacing spinner-only states.
5. THE Platform SHALL apply consistent micro-animations: hover lift on cards (translateY -2px, shadow increase), fade-in on page mount (opacity 0→1, 200ms), and slide-up on list item appearance (translateY 8px→0, 300ms).
6. THE Platform SHALL display a consistent toast notification system for success, error, warning, and info states, appearing in the bottom-right corner with auto-dismiss after 4 seconds.
7. THE Platform SHALL apply a consistent button hierarchy: primary (gradient fill), secondary (outlined), ghost (text only), and destructive (red fill), with consistent padding, border radius, and focus ring styles.
8. THE Platform SHALL display enterprise trust signals on the public landing page: security badges, uptime indicator, customer count, and a "SOC 2 Ready" or equivalent compliance signal.
9. WHEN a form field has a validation error, THE Platform SHALL display the error message inline below the field in red, with the field border turning red, without relying solely on browser-native validation UI.
10. THE Platform SHALL achieve a Lighthouse accessibility score of at least 90 on all primary pages, including proper ARIA labels, keyboard navigation, and sufficient colour contrast ratios.

---

### Requirement 10: Onboarding Flow

**User Story:** As a new user, I want a guided onboarding experience that helps me understand the platform's capabilities and complete my first meaningful action within 5 minutes, so that I can experience value before deciding to upgrade.

#### Acceptance Criteria

1. WHEN a new user completes signup, THE Platform SHALL present an onboarding checklist with at least four steps: complete profile, create first business, generate first campaign, and explore the AI Code Editor.
2. THE Onboarding_System SHALL track completion of each checklist step and persist progress in the user's profile.
3. WHEN all onboarding steps are complete, THE Onboarding_System SHALL display a completion celebration (confetti animation or equivalent) and dismiss the checklist.
4. THE Platform SHALL display contextual tooltips on first visit to each major feature area, explaining the feature's purpose in one sentence and dismissible with a single click.
5. WHEN a new user visits the Dashboard with zero businesses, THE Platform SHALL display the empty state with a prominent "Generate my first business" CTA rather than a generic empty list.
6. THE Onboarding_System SHALL send a welcome email within 5 minutes of signup containing: a personalised greeting, a link to the onboarding checklist, and three example use cases.

---

### Requirement 11: Strategic Monetisation — Usage Limits and Premium Tiers

**User Story:** As a platform operator, I want a usage limit and premium tier system that gates advanced features behind paid plans, so that the platform can generate sustainable revenue while offering a compelling free tier.

#### Acceptance Criteria

1. THE Platform SHALL enforce per-user usage limits for AI generation actions (business generation, campaign generation, code edits) based on the user's subscription tier.
2. WHEN a user reaches their tier's usage limit, THE Platform SHALL display a clear upgrade prompt identifying the limit reached, the current tier, and the benefits of upgrading.
3. THE Platform SHALL define at least three subscription tiers: Free (limited generations per month), Pro (unlimited generations, advanced features), and Enterprise (team workspaces, SSO, priority support).
4. THE Platform SHALL gate the following features behind the Pro tier or above: AI Studio multi-step generation, AI Code Editor RAG/codebase indexing, Deployment System, and Workspace team collaboration.
5. THE Platform SHALL display a visible tier badge in the sidebar user footer showing the user's current plan.
6. WHEN a user attempts to access a Pro-gated feature on the Free tier, THE Platform SHALL display a feature gate modal with a description of the feature, the required tier, and an upgrade CTA.
7. THE Usage_Limit_Service SHALL track and persist usage counts per user per billing period, resetting at the start of each new billing period.

---

### Requirement 12: AI Provider Fallback and Reliability

**User Story:** As a Developer or Founder, I want the AI orchestration layer to automatically fall back to available providers when the primary provider fails, so that AI features remain available even during provider outages.

#### Acceptance Criteria

1. THE AI_Orchestrator SHALL attempt requests using providers in a configurable priority order.
2. WHEN a Provider returns an error or times out, THE AI_Orchestrator SHALL automatically retry with the next available Provider in the priority order.
3. THE AI_Orchestrator SHALL implement a Circuit Breaker per Provider that opens after a configurable number of consecutive failures, preventing further requests to that Provider until the circuit half-opens.
4. WHEN all Providers are unavailable, THE AI_Orchestrator SHALL return a 503 Service Unavailable response with a descriptive error message.
5. THE AI_Orchestrator SHALL log each fallback event with: the failed Provider, the error type, the fallback Provider used, and the request trace ID.
6. THE AI_Orchestrator SHALL expose a health endpoint returning the current state of all Providers and the system-level fallback rate.
7. WHEN a Circuit Breaker transitions from open to half-open, THE AI_Orchestrator SHALL route a single test request to the Provider and close the circuit only if the test request succeeds.

---

### Requirement 13: Accessibility and Internationalisation Foundations

**User Story:** As a user with accessibility needs, I want the Platform to be navigable by keyboard and screen reader, so that I can use all core features without relying on a mouse.

#### Acceptance Criteria

1. THE Platform SHALL ensure all interactive elements (buttons, links, inputs, selects) are reachable and activatable via keyboard Tab and Enter/Space navigation.
2. THE Platform SHALL provide visible focus indicators on all interactive elements that meet WCAG 2.1 AA contrast requirements.
3. THE Platform SHALL provide ARIA labels for all icon-only buttons and controls that lack visible text labels.
4. THE Platform SHALL ensure all images and decorative icons have appropriate `alt` attributes or `aria-hidden="true"` as applicable.
5. THE Platform SHALL ensure colour is not the sole means of conveying information (e.g., error states use both colour and an icon or text label).
6. THE Platform SHALL support right-to-left (RTL) text direction as a future-ready foundation, using logical CSS properties (margin-inline, padding-inline) rather than directional properties (margin-left, padding-right) in new components.
