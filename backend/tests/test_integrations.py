import pytest


@pytest.mark.asyncio
async def test_list_integrations_includes_setup_metadata(client, auth_headers, generated_business):
    response = await client.get(f"/api/v1/integrations/{generated_business['id']}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    linkedin = next(item for item in data if item["platform"] == "linkedin")
    assert "state_label" in linkedin
    assert "redirect_uri" in linkedin
    assert "required_env_vars" in linkedin
    assert linkedin["redirect_uri"].endswith("/api/v1/integrations/linkedin/callback")


@pytest.mark.asyncio
async def test_connect_unconfigured_oauth_provider_returns_setup_required(client, auth_headers, generated_business, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "linkedin_client_id", None)
    monkeypatch.setattr(settings, "linkedin_client_secret", None)
    response = await client.post(
        "/api/v1/integrations/linkedin/connect",
        headers=auth_headers,
        json={"business_id": generated_business["id"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "setup_required"
    assert "LINKEDIN_CLIENT_ID" in data["required_env_vars"]
    assert "LINKEDIN_CLIENT_SECRET" in data["required_env_vars"]
    assert "LINKEDIN_REDIRECT_URI" in data["required_env_vars"]


@pytest.mark.asyncio
async def test_provider_settings_endpoint_returns_setup_metadata(client, auth_headers):
    response = await client.get("/api/v1/integrations/providers/linkedin/settings", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "linkedin"
    assert data["connect_mode"] == "oauth"
    assert "LINKEDIN_CLIENT_ID" in data["required_env_vars"]
    assert data["redirect_uri"].endswith("/api/v1/integrations/linkedin/callback")


@pytest.mark.asyncio
async def test_provider_settings_can_be_saved(client, auth_headers, tmp_path, monkeypatch):
    import app.api.routes.integrations as integrations_route

    monkeypatch.setattr(integrations_route, "BACKEND_ENV_PATH", tmp_path / ".env")
    response = await client.post(
        "/api/v1/integrations/providers/linkedin/settings",
        headers=auth_headers,
        json={"client_id": "linkedin-test-id", "client_secret": "linkedin-test-secret"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ready_to_connect"] is True
    assert data["client_id_configured"] is True
    assert data["client_secret_configured"] is True
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "LINKEDIN_REDIRECT_URI=http://localhost:8000/api/v1/integrations/linkedin/callback" in env_text
