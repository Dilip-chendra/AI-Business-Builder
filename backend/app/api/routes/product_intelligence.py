"""Research-backed product intelligence for AI Business Builder."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


REPORT_INTELLIGENCE = {
    "positioning": {
        "headline": "Autonomous growth operating system for local service businesses",
        "wedge": "Residential home services: HVAC, plumbing, electrical, and roofing operators under 20 employees.",
        "why_now": "The report identifies this segment as large, fragmented, lead-response dependent, and highly aligned with automated follow-up, local marketing, scheduling, review requests, and revenue attribution.",
        "not_just_ai": "AI Business Builder is positioned as a backend-owned execution system: integrations, approval gates, browser fallback, publishing attempts, and real measurement instead of isolated content generation.",
    },
    "market_opportunities": [
        {
            "title": "Home services growth automation",
            "detail": "HVAC, plumbing, electrical, and roofing businesses need faster lead response, local campaign execution, review generation, and booked-revenue tracking.",
            "priority": "P0",
        },
        {
            "title": "Integrations control plane",
            "detail": "OAuth, token refresh, encrypted token storage, audit logs, and internal tool endpoints are the production backbone competitors often hide behind brittle setup screens.",
            "priority": "P0",
        },
        {
            "title": "Browser fallback operator",
            "detail": "Browser automation should recover stale sessions, detect login/MFA checkpoints, capture artifacts, and stop in human-review states rather than claiming success.",
            "priority": "P1",
        },
        {
            "title": "Approval-to-measurement marketing loop",
            "detail": "Separate generation, review, publishing, and attribution so campaigns are optimized only from real events and provider responses.",
            "priority": "P0",
        },
    ],
    "customer_pain_points": [
        "Small operators lose leads because response, scheduling, and follow-up are manual.",
        "Marketing tools generate content but do not connect it to publishing, tracking, or booked revenue.",
        "OAuth setup, sender verification, scopes, and token expiry are confusing and brittle.",
        "Browser automation often stops at login pages without a recoverable workflow.",
        "Analytics dashboards fabricate or overstate performance when no real campaign events exist.",
    ],
    "competitor_gap_analysis": [
        {
            "competitor_pattern": "Content generators and social schedulers",
            "what_they_do_well": "Fast copy generation, templates, and simple approval workflows.",
            "missing": "Deep business context, real provider state, browser fallback, booked-revenue attribution.",
            "ai_business_builder_feature": "Campaign Mission Control with approval gates, provider readiness, real send/publish attempts, and analytics from actual events.",
            "priority": "P0",
        },
        {
            "competitor_pattern": "Automation platforms",
            "what_they_do_well": "Connect many apps and run deterministic workflows.",
            "missing": "Autonomous research, vertical strategy, AI-generated assets, and human-readable setup recovery.",
            "ai_business_builder_feature": "AI planner plus internal tool endpoints and setup-required diagnostics.",
            "priority": "P1",
        },
        {
            "competitor_pattern": "Browser agents",
            "what_they_do_well": "Can operate websites when APIs are unavailable.",
            "missing": "Production OAuth-first architecture, session vaults, artifacts, and verified completion states.",
            "ai_business_builder_feature": "Official API first, browser only as fallback with needs_login, needs_human, draft_ready, and publish_verified states.",
            "priority": "P1",
        },
    ],
    "roadmap": [
        {
            "phase": "0-90 days",
            "theme": "Production control plane",
            "tasks": [
                "Finish OAuth lifecycle, encrypted token vault, provider tests, and audit trail.",
                "Harden SendGrid/Gmail, Calendar, Notion, LinkedIn, and Browser Vault flows.",
                "Make Marketing metrics real-only and store every publish attempt.",
                "Ship home-services campaign templates for HVAC, plumbing, electrical, and roofing.",
            ],
        },
        {
            "phase": "3-6 months",
            "theme": "Verticalized growth OS",
            "tasks": [
                "Add lead capture, quote follow-up, review request, missed-call recovery, and local SEO workflows.",
                "Connect products, campaigns, landing pages, checkout, and analytics around booked revenue.",
                "Add campaign experiments and optimization recommendations from real events.",
            ],
        },
        {
            "phase": "6-12 months",
            "theme": "Defensible automation layer",
            "tasks": [
                "Package reusable playbooks for home-services agencies and multi-location operators.",
                "Add browser artifacts, trace replay, provider rate-limit handling, and queue-based retries.",
                "Turn accumulated campaign results into vertical AI playbooks.",
            ],
        },
    ],
    "implementation_tasks": [
        "Expose provider readiness and setup-required diagnostics in every integration and publish button.",
        "Create campaign assets as children of one campaign, not separate fake campaigns.",
        "Require approval before any live send, publish, or browser action.",
        "Use official APIs first; route to Browser Agent only when API is unavailable or user explicitly chooses browser mode.",
        "Surface report-backed home-services playbooks in Marketing Engine quick goals.",
    ],
}


@router.get("/report")
async def product_intelligence_report() -> dict:
    """Return the product-intelligence summary extracted from the hardening report."""
    return REPORT_INTELLIGENCE
