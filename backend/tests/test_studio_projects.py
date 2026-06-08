import pytest


pytestmark = pytest.mark.anyio


async def test_execute_prompt_applies_real_project_action(client, auth_headers, generated_business, monkeypatch):
    project_id = generated_business["project_id"]
    business_id = generated_business["id"]

    captured = {}

    async def fake_run_prompt(self, business_id_arg, prompt, current_user, brand_context=None):
        captured["business_id"] = business_id_arg
        captured["prompt"] = prompt
        captured["brand_context"] = brand_context or {}
        return {
            "status": "completed",
            "conversation_id": "conversation-1",
            "assistant_message": {
                "content": "Changed the page color system to black gold.",
                "created_at": "2026-06-07T10:00:00+00:00",
            },
            "action": {
                "action_type": "app_builder_project_update",
                "summary": "Changed the page color system to black gold.",
                "provider_used": "groq",
                "changed_files": [
                    "app/page.tsx",
                    "components/Hero.tsx",
                    "styles/theme.css",
                ],
                "version_id": "version-123",
                "preview_url": f"/landing/{business_id}?preview=1&v=version-123",
                "orchestration": {
                    "status": "completed",
                    "provider_used": "groq",
                    "completed_at": "2026-06-07T10:00:00+00:00",
                },
            },
        }

    monkeypatch.setattr("app.api.routes.studio_projects.AIStudioService.run_prompt", fake_run_prompt)

    response = await client.post(
        f"/api/v1/studio/projects/{project_id}/execute-prompt",
        json={
            "business_id": business_id,
            "project_id": project_id,
            "prompt": "change the page color to black and gold",
            "mode": "apply",
            "brand_context": {"source": "ai-studio-custom-prompt"},
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "applied"
    assert payload["business_id"] == business_id
    assert payload["project_id"] == project_id
    assert payload["provider"] == "groq"
    assert payload["changed_files"] == [
        "app/page.tsx",
        "components/Hero.tsx",
        "styles/theme.css",
    ]
    assert payload["changed_database_records"] == ["business_profile"]
    assert payload["preview_url"].startswith(f"/landing/{business_id}")
    assert payload["preview_version"] == "version-123"
    assert payload["version_id"] == "version-123"
    assert payload["timestamp"] == "2026-06-07T10:00:00+00:00"
    assert payload["conversation_id"] == "conversation-1"
    assert captured == {
        "business_id": business_id,
        "prompt": "change the page color to black and gold",
        "brand_context": {"source": "ai-studio-custom-prompt"},
    }


async def test_execute_prompt_rejects_stale_project_context(client, auth_headers, generated_business, monkeypatch):
    async def fake_run_prompt(*args, **kwargs):
        raise AssertionError("AI Studio should not run for a mismatched project id")

    monkeypatch.setattr("app.api.routes.studio_projects.AIStudioService.run_prompt", fake_run_prompt)

    stale_project_id = "00000000-0000-0000-0000-000000000000"
    response = await client.post(
        f"/api/v1/studio/projects/{stale_project_id}/execute-prompt",
        json={
            "business_id": generated_business["id"],
            "project_id": stale_project_id,
            "prompt": "change the page color to orange",
            "mode": "apply",
        },
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Selected business does not belong to this project"
