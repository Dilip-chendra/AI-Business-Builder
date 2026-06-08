from app.services.browser_agent.browser_memory import BrowserMemory
from app.services.browser_agent.action_parser import ActionParser
from app.services.browser_agent.planner import BrowserPlanner


def test_browser_memory_rejects_duplicate_clicks_on_same_page():
    memory = BrowserMemory()
    memory.observe_state(
        url="https://www.bing.com/search?q=fitness+seo&form=QBLH&cvid=123",
        tabs=[
            {
                "index": 0,
                "url": "https://www.bing.com/search?q=fitness+seo&form=QBLH&cvid=123",
                "active": True,
                "kind": "search",
            }
        ],
    )
    action = {"action": "click", "element_id": 88, "reason": "Open first result"}
    memory.add_step(
        step=1,
        action=action,
        thought="Opening the first search result",
        result="Opened tab",
        success=True,
        url="https://www.bing.com/search?q=fitness+seo&form=QBLH&cvid=123",
        metadata={"target_url": "https://grindsuccess.com/fitness-keywords/", "opened_in_new_tab": True},
    )

    reason = memory.duplicate_action_reason(
        action,
        current_url="https://www.bing.com/search?q=fitness+seo",
        tabs=[
            {
                "index": 0,
                "url": "https://www.bing.com/search?q=fitness+seo",
                "active": True,
                "kind": "search",
            },
            {
                "index": 1,
                "url": "https://grindsuccess.com/fitness-keywords/",
                "active": False,
                "kind": "source",
            },
        ],
    )

    assert reason is not None
    assert "already clicked" in reason.lower()


def test_browser_memory_normalizes_tracking_query_params():
    normalized = BrowserMemory.normalize_url(
        "https://www.bing.com/search?q=fitness+seo&form=QBLH&cvid=ABC123&sp=-1"
    )
    assert normalized == "https://www.bing.com/search?q=fitness+seo"


def test_planner_heuristic_skips_visited_search_result():
    planner = BrowserPlanner()
    dom_snapshot = {
        "url": "https://www.bing.com/search?q=fitness+seo",
        "title": "fitness seo - Search",
        "headings": ["Search results"],
        "text_excerpt": "SEO keyword lists for fitness coaching businesses",
        "elements": [
            {
                "id": 10,
                "tag": "a",
                "text": "Visited result",
                "href": "https://grindsuccess.com/fitness-keywords/",
            },
            {
                "id": 11,
                "tag": "a",
                "text": "Fresh result",
                "href": "https://copyblogger.com/fitness-seo-keywords/",
            },
        ],
    }
    action = planner._heuristic_action(
        goal="Find SEO keywords for fitness coaching businesses",
        dom_snapshot=dom_snapshot,
        vision_analysis={"blockers": []},
        memory_state={
            "active_url": "https://www.bing.com/search?q=fitness+seo",
            "visited_urls": [
                "https://www.bing.com/search?q=fitness+seo",
                "https://grindsuccess.com/fitness-keywords/",
            ],
            "opened_tabs": ["https://grindsuccess.com/fitness-keywords/"],
            "clicked_targets": [],
            "external_urls": ["https://grindsuccess.com/fitness-keywords/"],
            "tabs": [
                {
                    "index": 0,
                    "url": "https://www.bing.com/search?q=fitness+seo",
                    "active": True,
                    "kind": "search",
                }
            ],
            "extracted_urls": [],
        },
        extracted_context="No extracted data yet.",
        step_number=2,
        max_steps=10,
        error="Planner timed out",
    )

    assert action["action"] == "click"
    assert action["element_id"] == 11


def test_browser_memory_reports_research_progress():
    memory = BrowserMemory()
    memory.observe_state(url="https://example.com/pricing", tabs=[])
    memory.add_step(
        step=1,
        action={"action": "extract", "instruction": "Extract pricing details and plan names"},
        thought="Extract pricing evidence",
        result="Starter plan $19/month\nPro plan $49/month",
        success=True,
        url="https://example.com/pricing",
        metadata={},
    )

    progress = memory.research_progress(goal="Analyze pricing strategies", target_sources=3)

    assert progress["unique_sources"] == 1
    assert progress["unique_domains"] == 1
    assert progress["extracted_sources"] == 1
    assert progress["progress_score"] > 0


def test_browser_agent_targets_six_sources_for_research_goals():
    from app.services.browser_agent.browser_agent import BrowserAgent

    assert BrowserAgent._target_sources_for_goal("pricing_research") == 6
    assert BrowserAgent._target_sources_for_goal("keyword_research") == 6
    assert BrowserAgent._target_sources_for_goal("general_research") == 6
    assert BrowserAgent._target_sources_for_goal("publishing") == 1


def test_browser_agent_can_synthesize_when_budget_expires_with_useful_evidence():
    from app.services.browser_agent.browser_agent import BrowserAgent

    assert BrowserAgent._has_synthesis_ready_evidence(
        {
            "useful_sources": 2,
            "extracted_sources": 2,
            "evidence_density": 1.0,
            "structured_density": 0.0,
            "avg_quality": 0.3,
        }
    )
    assert BrowserAgent._has_synthesis_ready_evidence(
        {
            "useful_sources": 1,
            "extracted_sources": 1,
            "evidence_density": 1.5,
            "structured_density": 1.0,
            "avg_quality": 0.25,
        }
    )
    assert not BrowserAgent._has_synthesis_ready_evidence(
        {
            "useful_sources": 0,
            "extracted_sources": 1,
            "evidence_density": 0.0,
            "structured_density": 0.0,
            "avg_quality": 0.1,
        }
    )


def test_deterministic_planner_extracts_source_page_before_scrolling():
    planner = BrowserPlanner()
    action = planner.deterministic_research_action(
        goal="Research trending digital products in the productivity niche",
        dom_snapshot={
            "url": "https://example.com/productivity-digital-products",
            "title": "20 profitable digital products to sell in 2026",
            "headings": ["Digital product ideas", "Productivity templates", "AI workflow kits"],
            "text_excerpt": "A practical guide to productivity templates, Notion systems, AI workflow kits, planners, and digital products for creators in 2026.",
            "visible_text": "A practical guide to productivity templates, Notion systems, AI workflow kits, planners, and digital products for creators in 2026. These products are trending because teams want faster planning, automation, and focus.",
            "elements": [],
            "blockers": [],
        },
        memory_state={"extracted_urls": [], "rejected_source_urls": [], "tabs": []},
        extracted_context="No extracted data yet.",
        progress={"useful_sources": 0, "target_sources": 6},
    )

    assert action is not None
    assert action["action"] == "extract"


def test_deterministic_planner_uses_normalized_extracted_urls():
    planner = BrowserPlanner()
    action = planner.deterministic_research_action(
        goal="Research trending digital products in the productivity niche",
        dom_snapshot={
            "url": "https://example.com/productivity-digital-products/?utm_source=test",
            "title": "20 profitable digital products to sell in 2026",
            "headings": ["Digital product ideas"],
            "visible_text": "Long enough content about productivity digital products and trends.",
            "elements": [],
            "blockers": [],
        },
        memory_state={
            "extracted_urls": ["https://example.com/productivity-digital-products/"],
            "rejected_source_urls": [],
            "tabs": [],
        },
        extracted_context="Source: Example\nSummary: Already extracted.",
        progress={"useful_sources": 1, "target_sources": 6},
    )

    assert action is not None
    assert action["action"] != "extract"


def test_action_parser_defaults_search_engine_to_duckduckgo():
    parsed = ActionParser.parse_action('{"action":"search","query":"fitness seo"}')
    assert parsed["action"] == "search"
    assert parsed["search_engine"] == "duckduckgo"


def test_browser_memory_rejects_reclicking_same_search_result_after_tab_open():
    memory = BrowserMemory()
    action = {"action": "click", "element_id": 91}
    memory.add_step(
        step=1,
        action=action,
        thought="Open result",
        result="Opened source in new tab",
        success=True,
        url="https://seturon.io/blog/pricing-strategies-for-online-courses",
        metadata={
            "source_url": "https://duckduckgo.com/?q=pricing+strategies",
            "target_url": "https://seturon.io/blog/pricing-strategies-for-online-courses",
            "opened_in_new_tab": True,
        },
    )

    reason = memory.duplicate_action_reason(
        action,
        current_url="https://duckduckgo.com/?q=pricing+strategies",
        tabs=[],
    )

    assert reason is not None
    assert "already clicked" in reason.lower()


def test_planner_prefers_switching_to_unextracted_source_tab_before_searching_again():
    planner = BrowserPlanner()
    dom_snapshot = {
        "url": "https://duckduckgo.com/?q=fitness+seo",
        "title": "fitness seo at DuckDuckGo",
        "headings": ["Search results"],
        "text_excerpt": "Results for fitness seo",
        "elements": [],
        "page_height": 1200,
        "viewport": {"height": 900},
        "scroll_y": 100,
    }
    action = planner._heuristic_action(
        goal="Find SEO keywords for fitness coaching businesses",
        dom_snapshot=dom_snapshot,
        vision_analysis={"blockers": []},
        memory_state={
            "active_url": "https://duckduckgo.com/?q=fitness+seo",
            "visited_urls": ["https://duckduckgo.com/?q=fitness+seo"],
            "opened_tabs": ["https://copyblogger.com/fitness-seo-keywords/"],
            "clicked_targets": [],
            "external_urls": ["https://copyblogger.com/fitness-seo-keywords/"],
            "tabs": [
                {
                    "index": 0,
                    "url": "https://duckduckgo.com/?q=fitness+seo",
                    "normalized_url": "https://duckduckgo.com/?q=fitness+seo",
                    "active": True,
                    "kind": "search",
                },
                {
                    "index": 1,
                    "url": "https://copyblogger.com/fitness-seo-keywords/",
                    "normalized_url": "https://copyblogger.com/fitness-seo-keywords",
                    "active": False,
                    "kind": "source",
                },
            ],
            "extracted_urls": [],
        },
        extracted_context="No extracted data yet.",
        step_number=3,
        max_steps=12,
        error="Planner timed out",
    )

    assert action["action"] == "switch_tab"
    assert action["tab_index"] == 1


def test_planner_does_not_finish_keyword_research_after_single_source():
    planner = BrowserPlanner()
    dom_snapshot = {
        "url": "https://duckduckgo.com/?q=fitness+seo",
        "title": "fitness seo at DuckDuckGo",
        "headings": ["Search results"],
        "text_excerpt": "Results for fitness seo",
        "elements": [
            {
                "id": 15,
                "tag": "a",
                "text": "Second result",
                "href": "https://backlinko.com/fitness-seo-keywords",
            },
        ],
        "page_height": 1200,
        "viewport": {"height": 900},
        "scroll_y": 100,
    }
    action = planner._heuristic_action(
        goal="Find SEO keywords for fitness coaching businesses",
        dom_snapshot=dom_snapshot,
        vision_analysis={"blockers": []},
        memory_state={
            "active_url": "https://duckduckgo.com/?q=fitness+seo",
            "visited_urls": [
                "https://duckduckgo.com/?q=fitness+seo",
                "https://copyblogger.com/fitness-seo-keywords",
            ],
            "opened_tabs": [],
            "clicked_targets": [],
            "external_urls": ["https://copyblogger.com/fitness-seo-keywords"],
            "tabs": [
                {
                    "index": 0,
                    "url": "https://duckduckgo.com/?q=fitness+seo",
                    "normalized_url": "https://duckduckgo.com/?q=fitness+seo",
                    "active": True,
                    "kind": "search",
                },
            ],
            "extracted_urls": ["https://copyblogger.com/fitness-seo-keywords"],
        },
        extracted_context="Extraction step 1 from https://copyblogger.com/fitness-seo-keywords...",
        step_number=6,
        max_steps=12,
        error="Planner timed out",
    )

    assert action["action"] == "click"
    assert action["element_id"] == 15


def test_browser_memory_keeps_cached_search_results_from_successful_search():
    memory = BrowserMemory()
    memory.add_step(
        step=1,
        action={"action": "search", "query": "online course pricing"},
        thought="Search DuckDuckGo",
        result="Prepared DuckDuckGo result set",
        success=True,
        url="https://lite.duckduckgo.com/lite/?q=online+course+pricing",
        metadata={
            "search_results": [
                {"canonical_url": "https://example.com/pricing", "title": "Pricing Guide", "snippet": "Pricing models"},
                {"canonical_url": "https://example.org/plans", "title": "Course Plans", "snippet": "Plan comparison"},
            ]
        },
    )

    assert len(memory.summary()["cached_search_results"]) == 2


def test_planner_uses_cached_search_results_when_search_page_is_blocked():
    planner = BrowserPlanner()
    action = planner._heuristic_action(
        goal="Analyze pricing strategies for online course platforms",
        dom_snapshot={
            "url": "https://lite.duckduckgo.com/lite/?q=online+course+pricing",
            "title": "",
            "headings": [],
            "text_excerpt": "If this persists, please email us.",
            "elements": [],
            "search_results": [],
            "page_height": 800,
            "viewport": {"height": 800},
            "scroll_y": 0,
        },
        vision_analysis={"blockers": ["error getting results"]},
        memory_state={
            "active_url": "https://lite.duckduckgo.com/lite/?q=online+course+pricing",
            "visited_urls": ["https://lite.duckduckgo.com/lite/?q=online+course+pricing"],
            "opened_tabs": [],
            "clicked_targets": [],
            "external_urls": [],
            "tabs": [
                {
                    "index": 0,
                    "url": "https://lite.duckduckgo.com/lite/?q=online+course+pricing",
                    "normalized_url": "https://lite.duckduckgo.com/lite?q=online+course+pricing",
                    "active": True,
                    "kind": "search",
                }
            ],
            "extracted_urls": [],
            "cached_search_results": [
                {
                    "canonical_url": "https://verifyed.io/blog/pricing-strategies-for-online-courses",
                    "text": "5 Proven Pricing Strategies for Online Courses in 2025",
                    "snippet": "Pricing ranges and completion rates.",
                }
            ],
        },
        extracted_context="No extracted data yet.",
        step_number=2,
        max_steps=18,
        error="Planner timed out",
    )

    assert action["action"] == "open_tab"
    assert "verifyed.io" in action["url"]


def test_planner_skips_rejected_blocked_source_tabs():
    planner = BrowserPlanner()
    action = planner._heuristic_action(
        goal="Analyze pricing strategies for online course platforms",
        dom_snapshot={
            "url": "https://www.learningrevolution.net/how-to-price-online-courses",
            "title": "Checking your browser",
            "headings": [],
            "text_excerpt": "Checking your browser before accessing this page.",
            "elements": [],
            "search_results": [],
            "page_height": 800,
            "viewport": {"height": 800},
            "scroll_y": 0,
        },
        vision_analysis={"blockers": ["captcha"]},
        memory_state={
            "active_url": "https://www.learningrevolution.net/how-to-price-online-courses",
            "visited_urls": [],
            "opened_tabs": [
                "https://www.learningrevolution.net/how-to-price-online-courses",
                "https://www.verifyed.io/blog/pricing-strategies-for-online-courses",
            ],
            "clicked_targets": [],
            "external_urls": [],
            "tabs": [
                {
                    "index": 0,
                    "url": "https://lite.duckduckgo.com/lite/?q=online+course+pricing",
                    "normalized_url": "https://lite.duckduckgo.com/lite?q=online+course+pricing",
                    "active": False,
                    "kind": "search",
                },
                {
                    "index": 1,
                    "url": "https://www.learningrevolution.net/how-to-price-online-courses",
                    "normalized_url": "https://www.learningrevolution.net/how-to-price-online-courses",
                    "active": True,
                    "kind": "source",
                },
            ],
            "extracted_urls": [],
            "rejected_source_urls": ["https://www.learningrevolution.net/how-to-price-online-courses"],
            "cached_search_results": [],
        },
        extracted_context="No extracted data yet.",
        step_number=5,
        max_steps=18,
        error="Planner timed out",
    )

    assert action["action"] == "switch_tab"
    assert action["tab_index"] == 0


def test_browser_memory_marks_rejected_source_from_planner_switch():
    memory = BrowserMemory()
    memory.add_step(
        step=3,
        action={
            "action": "switch_tab",
            "tab_index": 0,
            "reject_current_source": True,
            "rejected_url": "https://studiofordigitalgrowth.com/blog/seo-keywords-for-coaches/",
            "reason": "This source is not yielding useful evidence, so return to DuckDuckGo and open a different website.",
        },
        thought="Reject weak source and return to search",
        result="Switched to tab 0",
        success=True,
        url="https://lite.duckduckgo.com/lite/?q=seo+keywords+fitness+coaching",
        metadata={},
    )

    summary = memory.summary()
    assert "https://studiofordigitalgrowth.com/blog/seo-keywords-for-coaches" in summary["rejected_source_urls"]
