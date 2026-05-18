import pytest

from app.core.cache import cache
from app.services.oauth_state_service import OAuthStateError, OAuthStateService


@pytest.mark.asyncio
async def test_oauth_state_can_be_issued_and_consumed_once():
    await cache.clear()
    service = OAuthStateService()
    token, payload = await service.issue(
        provider="linkedin",
        user_id="user-123",
        business_id="business-456",
        workspace_id="workspace-789",
    )

    consumed = await service.consume("linkedin", token)
    assert consumed.user_id == "user-123"
    assert consumed.business_id == "business-456"
    assert consumed.workspace_id == "workspace-789"
    assert consumed.integration_id == payload.integration_id

    with pytest.raises(OAuthStateError):
        await service.consume("linkedin", token)


@pytest.mark.asyncio
async def test_oauth_state_rejects_wrong_provider():
    await cache.clear()
    service = OAuthStateService()
    token, _payload = await service.issue(
        provider="linkedin",
        user_id="user-123",
        business_id="business-456",
        workspace_id=None,
    )

    with pytest.raises(OAuthStateError):
        await service.consume("twitter", token)
