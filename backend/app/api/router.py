from fastapi import APIRouter

from app.api.routes import (
    ai,
    ai_memory,
    ai_studio,
    agent_controller,
    agent_stream,
    agents,
    analytics,
    auth,
    billing,
    calendar,
    brand,
    businesses,
    code_editor,
    context,
    credentials,
    deployments,
    embeddings,
    experiments,
    integrations,
    jobs,
    marketing,
    onboarding,
    optimization,
    payments,
    product_intelligence,
    products,
    system,
    studio_projects,
    support,
    tools,
    tracking,
    uploads,
    usage_limits,
    workspaces,
)

api_router = APIRouter()

# ── Auth ──────────────────────────────────────────────────────────────────────
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(context.router, prefix="/context", tags=["context"])

# ── Core business flow ────────────────────────────────────────────────────────
api_router.include_router(businesses.router, prefix="/businesses", tags=["businesses"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(product_intelligence.router, prefix="/product-intelligence", tags=["product-intelligence"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(tracking.router, prefix="/tracking", tags=["tracking"])
api_router.include_router(calendar.router, prefix="/calendar", tags=["calendar"])

# ── AI ────────────────────────────────────────────────────────────────────────
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(ai_memory.router, prefix="/ai", tags=["ai-memory"])
api_router.include_router(ai_studio.router, prefix="/ai-studio", tags=["ai-studio"])
api_router.include_router(studio_projects.router, prefix="/studio", tags=["studio-projects"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(optimization.router, prefix="/optimize", tags=["optimization"])

# ── Agents ────────────────────────────────────────────────────────────────────
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(agent_controller.router, prefix="/agent", tags=["agent-controller"])
api_router.include_router(agent_stream.router, prefix="/agent", tags=["agent-stream"])

# ── Marketing Engine ──────────────────────────────────────────────────────────
api_router.include_router(marketing.router, prefix="/marketing", tags=["marketing"])

# ── Customer Support ──────────────────────────────────────────────────────────
api_router.include_router(support.router, prefix="/support", tags=["support"])

# ── A/B Testing ───────────────────────────────────────────────────────────────
api_router.include_router(experiments.router, prefix="/experiments", tags=["experiments"])

# ── Uploads ───────────────────────────────────────────────────────────────────
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])

# ── AI Code Editor ────────────────────────────────────────────────────────────
api_router.include_router(code_editor.router, prefix="/code-editor", tags=["code-editor"])
api_router.include_router(embeddings.router, prefix="/code-editor", tags=["embeddings"])

# ── Background Jobs ───────────────────────────────────────────────────────────
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
# ── Usage Limits ───────────────────────────────────────────────────────────────
api_router.include_router(usage_limits.router, prefix="/usage", tags=["usage-limits"])

# ── Workspaces and Projects ───────────────────────────────────────────────────
api_router.include_router(workspaces.router, prefix="", tags=["workspaces"])

# ── Deployments ───────────────────────────────────────────────────────────────
api_router.include_router(deployments.router, prefix="/deployments", tags=["deployments"])

# ── Onboarding ────────────────────────────────────────────────────────────────
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])

# ── Brand System ──────────────────────────────────────────────────────────────
api_router.include_router(brand.router, prefix="/brand", tags=["brand"])

# ── Platform Integrations ─────────────────────────────────────────────────────
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
api_router.include_router(credentials.router, prefix="/credentials", tags=["credentials"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])
