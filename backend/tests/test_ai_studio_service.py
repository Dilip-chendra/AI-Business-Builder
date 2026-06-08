from datetime import datetime, timezone
from types import SimpleNamespace
from pathlib import Path

import pytest

from app.services.ai_studio_service import AIStudioService
from app.services.ai_service import AIService


def test_ai_studio_maps_golden_button_prompt_to_amber_page_patch():
    business = SimpleNamespace(name="BrainSpark Academy")

    action = AIStudioService._deterministic_style_patch(
        business,
        "change the button to golden color",
    )

    assert action is not None
    assert action["page_patch"] == {"color_scheme": "amber"}
    assert "golden" in action["summary"].lower()


def test_ai_service_repairs_truncated_json_object():
    raw = '{"summary":"Updated hero","business_updates":{"headline":"Expert Home Services When You Need Them Most","subheading":"Reliable HVAC'

    parsed = AIService()._parse_json(raw)

    assert parsed["summary"] == "Updated hero"
    assert parsed["business_updates"]["headline"] == "Expert Home Services When You Need Them Most"
    assert parsed["business_updates"]["subheading"].startswith("Reliable HVAC")


def test_app_builder_color_prompt_changes_theme_without_rewriting_headline():
    business = SimpleNamespace(
        id="business-123",
        name="BrainSpark Academy",
        headline="Original Headline",
        page_content={"color_scheme": "indigo"},
    )
    service = AIStudioService(db=None)

    plan = service._deterministic_app_builder_plan(
        business,
        "change the color of the page to attractive",
        {},
    )

    assert plan is not None
    assert plan["business_updates"] == {}
    assert plan["page_content_patch"] == {"color_scheme": "black_gold"}
    assert "headline" not in plan["business_updates"]


def test_app_builder_guard_removes_ai_headline_for_style_only_prompt():
    business = SimpleNamespace(
        id="business-123",
        name="BrainSpark Academy",
        headline="Original Headline",
        page_content={"color_scheme": "indigo"},
    )
    service = AIStudioService(db=None)

    plan = service._guard_app_builder_plan(
        business,
        "change the color of the page to attractive",
        {
            "summary": "Changed the page style.",
            "business_updates": {"headline": "change the color of the page to attractive"},
            "page_content_patch": {},
            "files": [],
        },
    )

    assert plan["business_updates"] == {}
    assert plan["page_content_patch"]["color_scheme"] == "black_gold"


def test_app_builder_guard_keeps_style_prompt_from_injecting_copy_sections():
    business = SimpleNamespace(
        id="business-123",
        name="FitPro Coach",
        headline="Transform Your Body",
        page_content={"color_scheme": "indigo"},
    )
    service = AIStudioService(db=None)

    plan = service._guard_app_builder_plan(
        business,
        "update the color scheme to feel more attractive using orange color",
        {
            "summary": "Changed the page.",
            "business_updates": {
                "headline": "Modern Fitness Transformation for Busy Professionals",
                "subheading": "A rewritten offer the user did not ask for.",
            },
            "page_content_patch": {
                "color_scheme": "violet",
                "features": [{"title": "New feature", "description": "Injected copy"}],
                "social_proof": [{"name": "Alex", "quote": "Injected review", "rating": 5}],
            },
            "files": [],
        },
    )

    assert plan["business_updates"] == {}
    assert plan["page_content_patch"] == {"color_scheme": "amber"}


def test_app_builder_guard_honors_explicit_orange_over_wrong_model_theme():
    business = SimpleNamespace(
        id="business-123",
        name="ShopifyFlow",
        headline="Automate Your Shopify Store",
        page_content={"color_scheme": "indigo"},
    )
    service = AIStudioService(db=None)

    plan = service._guard_app_builder_plan(
        business,
        "update the color scheme to feel more attractive using orange color",
        {
            "summary": "Changed the page style.",
            "business_updates": {},
            "page_content_patch": {"color_scheme": "violet"},
            "files": [],
        },
    )

    assert plan["page_content_patch"]["color_scheme"] == "amber"


def test_app_builder_replaces_partial_theme_css_with_canonical_theme():
    business = SimpleNamespace(page_content={"color_scheme": "amber"})
    sync_service = SimpleNamespace(_theme_css=lambda: "FULL_THEME " + ".abb-primary .abb-card .abb-hero --abb-accent " * 80)

    content = AIStudioService._safe_app_builder_file_content(
        sync_service,
        "styles/theme.css",
        ":root { --abb-accent: #f59e0b; }\n/* ... rest of theme.css remains unchanged ... */",
    )

    assert content.startswith("FULL_THEME")
    assert "... rest of theme.css" not in content


def test_landing_patch_preserves_exact_colon_text_for_urgency():
    business = SimpleNamespace(name="Expert Home Services")

    action = AIStudioService._deterministic_landing_patch(
        business,
        "set the urgency line exactly to: Small home problems can become expensive fast. Schedule expert help today.",
    )

    assert action is not None
    assert action["field"] == "page_content"
    assert action["page_patch"]["urgency_text"] == "Small home problems can become expensive fast. Schedule expert help today"


def test_app_builder_accepts_brand_pivot_aliases_from_ai_provider():
    business = SimpleNamespace(
        id="business-123",
        name="FitPro Coach",
        headline="Transform Your Body",
        page_content={"color_scheme": "amber"},
    )
    service = AIStudioService(db=None)

    plan = service._guard_app_builder_plan(
        business,
        "Pivot this entire landing page from FitPro Coach to Expert Home Services",
        {
            "summary": "Pivoted the landing page to home services.",
            "business_updates": {
                "brand_name": "Expert Home Services",
                "audience": "Homeowners who need urgent or scheduled home repairs",
            },
            "hero": {
                "headline": "Expert Home Services When You Need Them Most",
                "subheadline": "Reliable HVAC, Plumbing, Electrical, and Roofing Solutions for Your Home",
                "cta": "Schedule a Service Call",
            },
            "page_content_patch": {
                "painPoints": ["Leaky pipes", "Broken AC units"],
                "services": [
                    {"title": "Emergency HVAC Repairs", "description": "Fast AC and heating support."},
                    {"title": "Licensed Plumbing Solutions", "description": "Repairs for leaks and clogged drains."},
                ],
                "reviews": [
                    {"name": "Maya R.", "role": "Homeowner", "quote": "They arrived quickly and fixed the leak.", "rating": 5}
                ],
            },
            "files": [],
        },
    )
    business_updates = AIStudioService._sanitize_business_updates(plan["business_updates"])
    page_patch = AIStudioService._sanitize_page_patch(plan["page_content_patch"])

    assert business_updates["name"] == "Expert Home Services"
    assert business_updates["target_audience"] == "Homeowners who need urgent or scheduled home repairs"
    assert business_updates["headline"] == "Expert Home Services When You Need Them Most"
    assert business_updates["subheading"].startswith("Reliable HVAC")
    assert business_updates["cta_text"] == "Schedule a Service Call"
    assert page_patch["pain_points"] == ["Leaky pipes", "Broken AC units"]
    assert page_patch["features"][0]["title"] == "Emergency HVAC Repairs"
    assert page_patch["social_proof"][0]["role"] == "Homeowner"


def test_ai_studio_routes_pivot_prompt_to_app_builder():
    plan = AIStudioService._plan_instruction(
        "Pivot this entire landing page from FitPro Coach to Expert Home Services"
    )

    assert plan["selected_tool"] == "app_builder"
    assert plan["intent"] == "prompt_to_app_update"


def test_app_builder_overlays_exact_user_intent_on_weak_provider_plan():
    business = SimpleNamespace(
        id="business-123",
        name="FitPro Coach",
        headline="Transform Your Body",
        subheading="Old fitness subheading",
        cta_text="Claim Free Consultation",
        description="Old description",
        product_pitch="Old pitch",
        page_content={"color_scheme": "amber"},
    )
    service = AIStudioService(db=None)
    instruction = """
    Pivot this entire landing page from a fitness coaching theme ("FitPro Coach")
    to a comprehensive Home Services brand called "Expert Home Services".
    Hero Section: Change the headline to "Expert Home Services When You Need Them Most"
    and the subheadline to "Reliable HVAC, Plumbing, Electrical, and Roofing Solutions for Your Home".
    Change the main CTA button text to "Schedule a Service Call".
    """

    weak_provider_plan = {
        "summary": "Updated page style.",
        "provider_used": "groq",
        "business_updates": {"headline": "Transform Your Body and Mind"},
        "page_content_patch": {"color_scheme": "violet"},
        "files": [],
    }
    local_patch = service._safe_local_app_builder_plan(business, instruction, {})

    merged = service._merge_app_builder_plans(weak_provider_plan, local_patch)
    guarded = service._guard_app_builder_plan(business, instruction, merged)

    assert guarded["business_updates"]["name"] == "Expert Home Services"
    assert guarded["business_updates"]["headline"] == "Expert Home Services When You Need Them Most"
    assert guarded["business_updates"]["subheading"] == "Reliable HVAC, Plumbing, Electrical, and Roofing Solutions for Your Home"
    assert guarded["business_updates"]["cta_text"] == "Schedule a Service Call"
    assert guarded["page_content_patch"]["features"][0]["title"] == "Emergency HVAC Repairs"
    assert guarded["provider_used"] == "groq+intent_safety_patch"


def test_local_app_builder_home_services_prompt_keeps_homeowner_reviews():
    business = SimpleNamespace(
        id="business-123",
        name="FitPro Coach",
        headline="Transform Your Body",
        subheading="Old fitness subheading",
        cta_text="Claim Free Consultation",
        description="Old description",
        product_pitch="Old pitch",
        page_content={"color_scheme": "amber"},
    )
    service = AIStudioService(db=None)
    instruction = """
    Pivot this entire landing page from a fitness coaching theme ("FitPro Coach") to a comprehensive Home Services brand called "Expert Home Services".
    Hero Section: Change the headline to "Expert Home Services When You Need Them Most" and the subheadline to "Reliable HVAC, Plumbing, Electrical, and Roofing Solutions for Your Home". Change the main CTA button text to "Schedule a Service Call".
    Social Proof / Reviews: Change the testimonials to reflect satisfied homeowners praising quick response times and quality workmanship.
    """

    plan = service._local_app_builder_plan(business, instruction, {})

    assert plan["business_updates"]["name"] == "Expert Home Services"
    assert plan["business_updates"]["headline"] == "Expert Home Services When You Need Them Most"
    assert plan["business_updates"]["subheading"] == "Reliable HVAC, Plumbing, Electrical, and Roofing Solutions for Your Home"
    assert plan["business_updates"]["cta_text"] == "Schedule a Service Call"
    assert plan["page_content_patch"]["features"][0]["title"] == "Emergency HVAC Repairs"
    assert all(item["role"] == "Homeowner" for item in plan["page_content_patch"]["social_proof"])
    assert "coaching" not in " ".join(item["quote"].lower() for item in plan["page_content_patch"]["social_proof"])


@pytest.mark.asyncio
async def test_app_builder_uses_runtime_provider_over_model_label(monkeypatch):
    business = SimpleNamespace(
        id="business-123",
        name="Expert Home Services",
        niche="Home services",
        target_audience="Homeowners",
        headline="Expert Home Services When You Need Them Most",
        subheading="Reliable HVAC, Plumbing, Electrical, and Roofing Solutions for Your Home",
        cta_text="Schedule a Service Call",
        page_content={"color_scheme": "black_gold"},
    )
    service = AIStudioService(db=None)

    async def fake_generate_text(self, prompt: str, trace_id: str | None = None, *, prefer_json: bool = False, task_type: str | None = None) -> str:
        self.last_provider = "groq"
        return '{"summary":"Kept page style current","provider_used":"ai_service_router","business_updates":{},"page_content_patch":{"color_scheme":"black_gold"},"files":[]}'

    monkeypatch.setattr(AIService, "generate_text", fake_generate_text)

    plan = await service._generate_app_builder_plan(
        business,
        "Update this landing page color scheme to black gold",
        {},
        {},
    )

    assert plan["provider_used"] == "groq"


def test_app_builder_lead_and_quote_prompt_creates_real_sections():
    business = SimpleNamespace(
        id="business-123",
        name="BrainSpark Academy",
        headline="Original Headline",
        page_content={"color_scheme": "violet"},
    )
    service = AIStudioService(db=None)

    plan = service._deterministic_app_builder_plan(
        business,
        "Add lead capture and quote request sections below the hero",
        {},
    )

    assert plan is not None
    assert plan["business_updates"] == {}
    assert "lead_capture" in plan["page_content_patch"]
    assert "quote_request" in plan["page_content_patch"]


def test_app_builder_orange_prompt_uses_orange_amber_not_black_gold():
    business = SimpleNamespace(
        id="business-123",
        name="BrainSpark Academy",
        headline="Original Headline",
        page_content={"color_scheme": "indigo"},
    )
    service = AIStudioService(db=None)

    plan = service._deterministic_app_builder_plan(
        business,
        "update the color scheme to a more modern look using the orange theme",
        {},
    )

    assert plan is not None
    assert plan["page_content_patch"]["color_scheme"] == "amber"


def test_local_app_builder_custom_service_prompt_creates_distinct_sections():
    business = SimpleNamespace(
        id="business-123",
        name="HomeFix",
        headline="Original Headline",
        subheading="Original subheading",
        cta_text="Get Started",
        description="Old description",
        product_pitch="Old pitch",
        page_content={"color_scheme": "indigo"},
    )
    service = AIStudioService(db=None)

    plan = service._local_app_builder_plan(
        business,
        "Reposition this page around booked service calls and fast follow-up for homeowners",
        {},
    )

    assert plan["business_updates"]["cta_text"] == "Request a Fast Quote"
    assert "lead_capture" in plan["page_content_patch"]
    assert "quote_request" in plan["page_content_patch"]
    assert plan["page_content_patch"]["color_scheme"] == "amber"


def test_local_app_builder_unknown_visual_prompt_still_applies_visible_update():
    business = SimpleNamespace(
        id="business-123",
        name="FitPro Coach",
        headline="Transform Your Body",
        subheading="Old subheading",
        cta_text="Get Started",
        description="Old description",
        product_pitch="Old pitch",
        page_content={"color_scheme": "indigo"},
    )
    service = AIStudioService(db=None)

    plan = service._local_app_builder_plan(
        business,
        "Make the upper half feel sharper and more trustworthy for visitors",
        {},
    )

    assert plan["business_updates"] == {}
    assert plan["page_content_patch"]["color_scheme"] == "black_gold"
    assert plan["page_content_patch"]["features"][0]["title"] == "Sharper First Impression"
    assert "custom prompt" in plan["summary"].lower()


def test_local_app_builder_exact_home_services_pivot_preserves_requested_copy():
    business = SimpleNamespace(
        id="business-123",
        name="FitPro Coach",
        headline="Transform Your Body",
        subheading="Old fitness subheading",
        cta_text="Claim Free Consultation",
        description="Old description",
        product_pitch="Old pitch",
        page_content={"color_scheme": "amber"},
    )
    service = AIStudioService(db=None)

    plan = service._local_app_builder_plan(
        business,
        """
        Pivot this entire landing page from a fitness coaching theme to a comprehensive
        Home Services brand called "Expert Home Services". Change the headline to
        "Expert Home Services When You Need Them Most" and the subheadline to
        "Reliable HVAC, Plumbing, Electrical, and Roofing Solutions for Your Home".
        Change the main CTA button text to "Schedule a Service Call". Replace fitness
        struggles with leaky pipes, broken AC units, outdated electrical, and roof leaks.
        """,
        {},
    )

    assert plan["business_updates"]["name"] == "Expert Home Services"
    assert plan["business_updates"]["headline"] == "Expert Home Services When You Need Them Most"
    assert plan["business_updates"]["subheading"] == "Reliable HVAC, Plumbing, Electrical, and Roofing Solutions for Your Home"
    assert plan["business_updates"]["cta_text"] == "Schedule a Service Call"
    assert "Leaky pipes" in plan["page_content_patch"]["pain_points"][0]
    assert plan["page_content_patch"]["features"][0]["title"] == "Emergency HVAC Repairs"
    assert plan["page_content_patch"]["social_proof"][0]["role"] == "Homeowner"


@pytest.mark.asyncio
async def test_app_builder_recovers_when_provider_returns_unstructured_output(monkeypatch):
    business = SimpleNamespace(
        id="business-123",
        name="FitPro Coach",
        headline="Transform Your Body",
        subheading="Old fitness subheading",
        cta_text="Claim Free Consultation",
        description="Old description",
        product_pitch="Old pitch",
        page_content={"color_scheme": "amber"},
    )
    service = AIStudioService(db=None)

    async def fake_generate_text(self, *args, **kwargs):
        raise ValueError("Could not parse JSON from AI response: Unterminated string")

    monkeypatch.setattr(AIService, "generate_text", fake_generate_text)

    current_files = {"app/page.tsx": "export default function Page() { return null }"}
    try:
        provider_plan = await service._generate_app_builder_plan(
            business,
            "Pivot this landing page to Expert Home Services for HVAC, Plumbing, Electrical, and Roofing.",
            {},
            current_files,
        )
    except Exception:
        provider_plan = service._local_app_builder_plan(
            business,
            "Pivot this landing page to Expert Home Services for HVAC, Plumbing, Electrical, and Roofing.",
            current_files,
        )

    guarded = service._guard_app_builder_plan(
        business,
        "Pivot this landing page to Expert Home Services for HVAC, Plumbing, Electrical, and Roofing.",
        provider_plan,
    )

    assert guarded["business_updates"]["name"] == "Expert Home Services"
    assert guarded["business_updates"]["headline"] == "Expert Home Services When You Need Them Most"
    assert guarded["page_content_patch"]["features"][0]["title"] == "Emergency HVAC Repairs"


@pytest.mark.asyncio
async def test_execute_app_builder_applies_local_recovery_after_provider_failure(monkeypatch, tmp_path):
    business = SimpleNamespace(
        id="business-123",
        name="FitPro Coach",
        niche="Health and wellness",
        target_audience="Busy professionals",
        headline="Transform Your Body",
        subheading="Old fitness subheading",
        cta_text="Claim Free Consultation",
        description="Old description",
        product_pitch="Old pitch",
        brand_tone="Motivational",
        monetization_model="consultation",
        seo_title="FitPro Coach",
        seo_description="Fitness coaching",
        page_content={"color_scheme": "amber"},
        updated_at=None,
    )
    user = SimpleNamespace(id="user-123")

    class FakeDb:
        def add(self, _obj):
            return None

        async def commit(self):
            return None

        async def refresh(self, _obj):
            return None

    class FakeSync:
        def __init__(self, _business):
            self.root = Path(tmp_path)

        def ensure_scaffold(self):
            (self.root / "app").mkdir(parents=True, exist_ok=True)
            (self.root / "components").mkdir(parents=True, exist_ok=True)
            (self.root / "styles").mkdir(parents=True, exist_ok=True)
            (self.root / "data").mkdir(parents=True, exist_ok=True)
            (self.root / "app/page.tsx").write_text("export default function Page() { return null }", encoding="utf-8")
            (self.root / "components/Hero.tsx").write_text("export function Hero() { return <section /> }", encoding="utf-8")
            (self.root / "styles/theme.css").write_text(":root { --abb-accent: #f59e0b; }", encoding="utf-8")
            (self.root / "data/business.json").write_text("{}", encoding="utf-8")

        def sync_business_profile(self):
            return ["data/business.json", "studio/business-profile.json"]

        def _theme_css(self):
            return "FULL_THEME " + ".abb-primary .abb-card .abb-hero --abb-accent " * 80

    class FakeVersionService:
        def __init__(self, _db):
            pass

        async def create_version(self, **_kwargs):
            return SimpleNamespace(id="version-123", version_number=1)

    async def fake_generate_plan(self, *_args, **_kwargs):
        raise ValueError("Could not parse JSON from AI response: Unterminated string")

    async def fake_cache_delete(_key):
        return None

    monkeypatch.setattr("app.services.ai_studio_service.ProjectSyncService", FakeSync)
    monkeypatch.setattr("app.services.ai_studio_service.CodeVersionService", FakeVersionService)
    monkeypatch.setattr(AIStudioService, "_generate_app_builder_plan", fake_generate_plan)
    monkeypatch.setattr("app.services.ai_studio_service.cache.delete", fake_cache_delete)

    result = await AIStudioService(FakeDb())._execute_app_builder(
        business,
        user,
        """
        Pivot this entire landing page from a fitness coaching theme ("FitPro Coach")
        to a comprehensive Home Services brand called "Expert Home Services".
        Change the headline to "Expert Home Services When You Need Them Most"
        and the subheadline to "Reliable HVAC, Plumbing, Electrical, and Roofing Solutions for Your Home".
        Change the main CTA button text to "Schedule a Service Call".
        """,
        {},
    )

    assert result["action_type"] == "app_builder_project_update"
    assert result["version_id"] == "version-123"
    assert business.name == "Expert Home Services"
    assert business.headline == "Expert Home Services When You Need Them Most"
    assert business.cta_text == "Schedule a Service Call"
    assert business.page_content["features"][0]["title"] == "Emergency HVAC Repairs"
    assert "components/Hero.tsx" in result["changed_files"]


def test_ai_studio_normalizes_color_button_instruction_to_page_content():
    assert AIStudioService._normalize_field("", "change the button to golden color") == "page_content"


def test_ai_studio_extracts_explicit_headline_prompt():
    business = SimpleNamespace(name="BrainSpark Academy", niche="study coaching")

    action = AIStudioService._deterministic_landing_patch(
        business,
        'change the headline to "Unlock Exam Confidence Today"',
    )

    assert action is not None
    assert action["field"] == "headline"
    assert action["new_value"] == "Unlock Exam Confidence Today"


def test_ai_studio_updates_cta_text_without_ai_provider():
    business = SimpleNamespace(name="BrainSpark Academy")

    action = AIStudioService._deterministic_landing_patch(
        business,
        'change button text to "Start Gold Trial"',
    )

    assert action is not None
    assert action["field"] == "cta_text"
    assert action["new_value"] == "Start Gold Trial"


def test_ai_studio_builds_visible_urgency_page_patch():
    business = SimpleNamespace(name="BrainSpark Academy")

    action = AIStudioService._deterministic_landing_patch(
        business,
        "add urgency text about finals week",
    )

    assert action is not None
    assert action["field"] == "page_content"
    assert "urgency_text" in action["page_patch"]
    assert "Finals season" in action["page_patch"]["urgency_text"]


def test_ai_studio_builds_premium_page_patch():
    business = SimpleNamespace(name="BrainSpark Academy")

    action = AIStudioService._deterministic_landing_patch(
        business,
        "make the page feel more premium and modern",
    )

    assert action is not None
    assert action["field"] == "page_content"
    assert action["page_patch"]["trust_badges"]
    assert action["page_patch"]["features"]


def test_ai_studio_detects_code_workspace_instruction():
    assert AIStudioService._looks_like_code_instruction("edit the Hero component to make the CTA bigger")
    assert AIStudioService._looks_like_code_instruction("modify styles/theme.css for better spacing")
    assert not AIStudioService._looks_like_code_instruction("change the landing page headline")


def test_ai_studio_selects_workspace_file_from_instruction(tmp_path):
    root = tmp_path
    (root / "app").mkdir()
    (root / "components").mkdir()
    (root / "styles").mkdir()
    (root / "app" / "page.tsx").write_text("page", encoding="utf-8")
    (root / "components" / "Hero.tsx").write_text("hero", encoding="utf-8")
    (root / "styles" / "theme.css").write_text("css", encoding="utf-8")

    assert AIStudioService._select_workspace_file(root, "edit the hero component") == "components/Hero.tsx"
    assert AIStudioService._select_workspace_file(root, "make the layout CSS more modern") == "styles/theme.css"
    assert AIStudioService._select_workspace_file(root, "update the landing page section") == "app/page.tsx"


def test_ai_studio_detects_research_instruction():
    assert AIStudioService._looks_like_browser_research_instruction("research top competitors for fitness coaching")
    assert AIStudioService._looks_like_browser_research_instruction("find SEO keyword trends on the web")
    assert not AIStudioService._looks_like_browser_research_instruction("change the button to gold")


def test_ai_studio_plans_prompt_before_execution():
    plan = AIStudioService._plan_instruction("create a LinkedIn campaign for my offer")

    assert plan["selected_tool"] == "marketing_engine"
    assert plan["intent"] == "marketing_generation"
    assert "campaign" in plan["reason"].lower()


def test_ai_studio_routes_visual_builder_prompts_to_app_builder():
    plan = AIStudioService._plan_instruction("Change the hero background to black and gold")

    assert plan["selected_tool"] == "app_builder"
    assert plan["intent"] == "prompt_to_app_update"


def test_local_app_builder_generates_visible_preview_patch():
    business = SimpleNamespace(
        id="business-123",
        name="FitPro Coach",
        headline="Old headline",
        subheading="Old subheading",
        cta_text="Get Started",
        description="Old description",
        product_pitch="Old pitch",
    )
    service = AIStudioService(db=None)

    plan = service._local_app_builder_plan(
        business,
        "Make this page look like a premium fitness coaching landing page with black and gold pricing and testimonials",
        {},
    )

    assert plan["page_content_patch"]["color_scheme"] == "black_gold"
    assert plan["business_updates"]["headline"].startswith("Premium Fitness Coaching")
    assert len(plan["page_content_patch"]["pricing_tiers"]) == 3
    assert len(plan["page_content_patch"]["social_proof"]) == 3
    assert {item["path"] for item in plan["files"]} == {"styles/theme.css", "components/Hero.tsx", "app/page.tsx"}


def test_local_app_builder_cta_only_prompt_does_not_rewrite_headline():
    business = SimpleNamespace(
        id="business-123",
        name="FitPro Coach",
        headline="FitPro Coach",
        subheading="Old subheading",
        cta_text="Get Started",
        description="Old description",
        product_pitch="Old pitch",
    )
    service = AIStudioService(db=None)

    plan = service._local_app_builder_plan(
        business,
        "Change CTA text to Book My Free Coaching Call",
        {},
    )

    assert plan["business_updates"] == {"cta_text": "Book My Free Coaching Call"}
    assert "headline" not in plan["business_updates"]


def test_local_app_builder_attractive_color_prompt_does_not_rewrite_copy():
    business = SimpleNamespace(
        id="business-123",
        name="FitPro Coach",
        headline="Transform Your Body",
        subheading="Old subheading",
        cta_text="Get Started",
        description="Old description",
        product_pitch="Old pitch",
        page_content={"color_scheme": "amber"},
    )
    service = AIStudioService(db=None)

    plan = service._local_app_builder_plan(
        business,
        "change the color of the page to attractive",
        {},
    )

    assert plan["business_updates"] == {}
    assert plan["page_content_patch"]["color_scheme"] == "black_gold"
    assert plan["page_content_patch"]["trust_badges"]


def test_app_builder_guard_strips_provider_copy_when_prompt_is_style_only():
    business = SimpleNamespace(
        id="business-123",
        name="FitPro Coach",
        headline="Transform Your Body",
        subheading="Old subheading",
        cta_text="Get Started",
        description="Old description",
        product_pitch="Old pitch",
        page_content={"color_scheme": "amber"},
    )
    provider_plan = {
        "summary": "Updated page style",
        "business_updates": {
            "headline": "change the color of the page to attractive",
            "subheading": "A new premium offer",
        },
        "page_content_patch": {
            "features": [{"title": "Wrong copy", "description": "Should not appear", "icon_hint": "star"}],
        },
        "files": [],
    }

    guarded = AIStudioService(db=None)._guard_app_builder_plan(
        business,
        "change the color of the page to attractive",
        provider_plan,
    )

    assert guarded["business_updates"] == {}
    assert guarded["page_content_patch"] == {"color_scheme": "black_gold"}


def test_ai_studio_attaches_prompt_and_tool_trace_to_action():
    business = SimpleNamespace(id="business-123", name="BrainSpark Academy")
    started_at = datetime.now(timezone.utc)
    plan = AIStudioService._plan_instruction("change the button to golden color")

    action = AIStudioService._attach_orchestration_trace(
        {
            "action_type": "business_profile_update",
            "summary": "Updated button color.",
            "version_id": "version-123",
            "updated_files": ["studio/business-profile.json"],
        },
        plan,
        business,
        "change the button to golden color",
        started_at,
        "completed",
    )

    trace = action["orchestration"]
    assert trace["instruction"] == "change the button to golden color"
    assert trace["selected_tool"] == "app_builder"
    assert trace["status"] == "completed"
    assert trace["version_id"] == "version-123"
    assert trace["updated_files"] == ["studio/business-profile.json"]
    assert any(step["label"] == "Backend action executed" for step in trace["steps"])
