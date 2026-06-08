import pytest
from sqlalchemy import select

from app.api.deps import get_db
from app.main import app
from app.models.integration_account import IntegrationAccount
from app.services.integration_account_service import IntegrationAccountService


@pytest.mark.anyio
async def test_credential_vault_encrypts_and_masks_secret_fields(client, auth_headers):
    save_response = await client.post(
        "/api/v1/credentials/linkedin",
        json={
            "login_email": "owner@example.com",
            "phone": "5551239999",
            "password": "super-secret-password",
        },
        headers=auth_headers,
    )

    assert save_response.status_code == 200
    payload = save_response.json()
    assert payload["provider"] == "linkedin"
    assert "password" not in payload
    assert payload["identifier_preview"] == "ow***@example.com"

    list_response = await client.get("/api/v1/credentials", headers=auth_headers)
    assert list_response.status_code == 200
    listed = {item["provider"]: item for item in list_response.json()}
    assert listed["linkedin"]["status"] == "configured"
    assert "password" not in listed["linkedin"]

    override_db = app.dependency_overrides[get_db]
    async for db in override_db():
        result = await db.execute(select(IntegrationAccount).where(IntegrationAccount.platform == "linkedin"))
        account = result.scalar_one()
        assert account.password_enc != "super-secret-password"
        assert account.login_identifier_enc != "owner@example.com"
        revealed = IntegrationAccountService(db).reveal(account)
        assert revealed["email"] == "owner@example.com"
        assert revealed["phone"] == "5551239999"
        assert revealed["password"] == "super-secret-password"
        break


@pytest.mark.anyio
async def test_credential_vault_test_login_never_returns_password(client, auth_headers):
    await client.post(
        "/api/v1/credentials/instagram",
        json={"login_email": "owner@example.com", "password": "secret"},
        headers=auth_headers,
    )

    test_response = await client.post(
        "/api/v1/credentials/instagram/test-login",
        headers=auth_headers,
    )

    assert test_response.status_code == 200
    payload = test_response.json()
    assert payload["status"] == "connected"
    assert "password" not in payload
