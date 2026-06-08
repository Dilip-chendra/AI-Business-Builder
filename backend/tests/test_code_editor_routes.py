import pytest


@pytest.mark.anyio
async def test_ai_edit_uses_selected_workspace_file_context(client, auth_headers, generated_business, monkeypatch):
    business_id = generated_business["id"]

    files_response = await client.get(
        f"/api/v1/code-editor/files?business_id={business_id}",
        headers=auth_headers,
    )
    assert files_response.status_code == 200

    read_response = await client.get(
        f"/api/v1/code-editor/file?business_id={business_id}&path=components/Hero.tsx",
        headers=auth_headers,
    )
    assert read_response.status_code == 200
    original = read_response.json()["content"]

    captured_prompts = []

    async def fake_generate_text(self, prompt: str, task_type: str = "general", **kwargs):
        captured_prompts.append(prompt)
        if "Workspace file path: components/Hero.tsx" in prompt:
            return original.replace("Launch", "Ship", 1)
        return "Changed the selected Hero component wording."

    monkeypatch.setattr("app.services.ai_service.AIService.generate_text", fake_generate_text)

    edit_response = await client.post(
        "/api/v1/code-editor/ai-edit",
        json={
            "business_id": business_id,
            "path": "components/Hero.tsx",
            "code": original,
            "instruction": "Change the hero wording from Launch to Ship",
            "language": "typescript",
        },
        headers=auth_headers,
    )

    assert edit_response.status_code == 200
    payload = edit_response.json()
    assert payload["path"] == "components/Hero.tsx"
    assert payload["updated_code"] != original
    assert any("Current code:" in prompt for prompt in captured_prompts)


@pytest.mark.anyio
async def test_ai_edit_extracts_fenced_code_before_saving(client, auth_headers, generated_business, monkeypatch):
    business_id = generated_business["id"]

    read_response = await client.get(
        f"/api/v1/code-editor/file?business_id={business_id}&path=components/Hero.tsx",
        headers=auth_headers,
    )
    assert read_response.status_code == 200
    original = read_response.json()["content"]
    updated = original.replace("Launch", "Convert", 1)
    if updated == original:
        updated = original.replace("business.cta_text", '"Convert Now"', 1)

    async def fake_generate_text(self, prompt: str, task_type: str = "general", **kwargs):
        if "In one sentence" in prompt:
            return "Updated the hero CTA wording."
        return f"Here is the updated file:\n```tsx\n{updated}\n```"

    monkeypatch.setattr("app.services.ai_service.AIService.generate_text", fake_generate_text)

    edit_response = await client.post(
        "/api/v1/code-editor/ai-edit",
        json={
            "business_id": business_id,
            "path": "components/Hero.tsx",
            "code": original,
            "instruction": "Change the hero CTA wording",
            "language": "typescript",
        },
        headers=auth_headers,
    )

    assert edit_response.status_code == 200
    payload = edit_response.json()
    assert payload["updated_code"].strip() == updated.strip()
    assert "```" not in payload["updated_code"]


@pytest.mark.anyio
async def test_ai_edit_rejects_explanation_only_output_without_saving(client, auth_headers, generated_business, monkeypatch):
    business_id = generated_business["id"]

    read_response = await client.get(
        f"/api/v1/code-editor/file?business_id={business_id}&path=components/Hero.tsx",
        headers=auth_headers,
    )
    assert read_response.status_code == 200
    original = read_response.json()["content"]

    async def fake_generate_text(self, prompt: str, task_type: str = "general", **kwargs):
        return "Here is what I changed: I made the hero CTA more attractive."

    monkeypatch.setattr("app.services.ai_service.AIService.generate_text", fake_generate_text)

    edit_response = await client.post(
        "/api/v1/code-editor/ai-edit",
        json={
            "business_id": business_id,
            "path": "components/Hero.tsx",
            "code": original,
            "instruction": "Make the hero CTA more attractive",
            "language": "typescript",
        },
        headers=auth_headers,
    )

    assert edit_response.status_code == 422
    assert "explanation text" in edit_response.json()["detail"]

    reread_response = await client.get(
        f"/api/v1/code-editor/file?business_id={business_id}&path=components/Hero.tsx",
        headers=auth_headers,
    )
    assert reread_response.status_code == 200
    assert reread_response.json()["content"] == original
