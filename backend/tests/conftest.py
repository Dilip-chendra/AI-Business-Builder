"""Shared pytest fixtures for the Autonomous Business Builder test suite."""
import sys
from unittest.mock import MagicMock

# ── Block Redis BEFORE any app module is imported ─────────────────────────────
# This must happen before `from app.xxx import ...` so the cache singleton
# never attempts a real TCP connection to Redis.
_fake_redis_client = MagicMock()
_fake_redis_client.ping.side_effect = ConnectionRefusedError("Redis disabled in tests")
_fake_redis_module = MagicMock()
_fake_redis_module.from_url.return_value = _fake_redis_client
sys.modules["redis"] = _fake_redis_module  # override, not setdefault

# ── Now safe to import app modules ────────────────────────────────────────────
import pytest  # noqa: E402
from httpx import AsyncClient, ASGITransport  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.api.deps import get_db  # noqa: E402
from app.core.config import settings  # noqa: E402
import app.db.base  # noqa: F401, E402 – registers all ORM models with Base.metadata
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.services.ai_service import AIService  # noqa: E402

# Disable rate limiting and Redis for tests
settings.rate_limit_requests = 10000
# Force in-memory cache — must be set after import, before any cache calls
from app.core.cache import cache as _cache  # noqa: E402
_cache._use_redis = False


@pytest.fixture(autouse=True)
def mock_real_ai_provider(monkeypatch):
    """Tests simulate a reachable provider without enabling app-level fake fallbacks.

    Also patches password hashing to avoid bcrypt computation overhead in tests.
    """
    import app.core.security as security_module

    monkeypatch.setattr(security_module, "hash_password", lambda plain: f"test-hash:{plain}")
    monkeypatch.setattr(security_module, "verify_password", lambda plain, hashed: hashed == f"test-hash:{plain}")

    async def local_generate(self, prompt: str, **kwargs) -> str:
        if "headline, cta_text, pricing_note, positioning_note" in prompt:
            return '{"headline":"Win more qualified customers","cta_text":"Start your launch","pricing_note":"Test a simple entry offer.","positioning_note":"Lead with the strongest audience pain."}'
        if "headline, cta_text, reason, insight" in prompt:
            return '{"headline":"Launch with a sharper promise","cta_text":"Start your launch","reason":"The page needs a clearer conversion path.","insight":"Improve the promise before scaling traffic."}'
        if "summary, insight, action, priority" in prompt:
            return '{"summary":"Package the first offer before scaling acquisition.","insight":"The business needs a monetizable product ladder.","action":"Create a starter offer and a premium upgrade.","priority":"high"}'
        if "headline, body, cta" in prompt:
            return '{"headline":"Launch faster","body":"Turn your idea into a sellable offer.","cta":"Start now"}'
        if "key insight" in prompt:
            return '{"insight":"Focus on the conversion bottleneck before increasing traffic."}'
        if "posts as an array" in prompt:
            return '{"posts":["Launch the offer today.","Validate faster with a clear page.","Turn interest into revenue."]}'
        if "SEO outline" in prompt:
            return '{"title":"How to launch faster","meta_description":"A practical launch guide.","sections":["Positioning","Offer","Page","Traffic","Conversion"]}'
        if "email campaign" in prompt:
            return '{"subject":"Launch faster","preview":"Your business can ship this week.","body":"Here is a practical path to launch."}'
        # Default: full business JSON
        return '{"name":"Productivity Launch Studio","niche":"productivity tools","description":"A focused platform for turning productivity ideas into sellable digital products.","target_audience":"remote workers","monetization_model":"Digital kits and subscriptions","brand_tone":"practical and trustworthy","headline":"Launch a productivity product faster","subheading":"Build the page, product, and checkout foundation in one workflow.","product_pitch":"A complete starter kit for validating productivity products.","cta_text":"Build my business","seo_title":"Productivity Launch Studio","seo_description":"AI generated launch assets for productivity businesses."}'

    monkeypatch.setattr(AIService, "local_generate", local_generate)

    # Make Ollama appear available so local_generate is always tried in tests
    # (avoids a real HTTP call to localhost:11434 during test runs)
    async def ollama_available(self) -> bool:
        return True

    monkeypatch.setattr(AIService, "_ollama_available", ollama_available)


@pytest.fixture()
async def client():
    """Async test client backed by an in-memory SQLite database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    TestingSession = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_db():
        async with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture()
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    """Create a user and return auth headers with JWT token."""
    response = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "testuser@example.com",
            "password": "testpass123",
            "full_name": "Test User",
        },
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
async def auth_client(client: AsyncClient, auth_headers: dict[str, str]) -> tuple[AsyncClient, dict[str, str]]:
    """Return a tuple of (client, auth_headers) for authenticated tests."""
    return client, auth_headers


@pytest.fixture()
async def generated_business(client: AsyncClient, auth_headers: dict[str, str]) -> dict:
    """Create and return a generated business for use in other tests."""
    response = await client.post(
        "/api/v1/businesses/generate",
        json={"interests": "productivity tools", "target_audience": "remote workers"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
async def created_product(client: AsyncClient, auth_headers: dict[str, str], generated_business: dict) -> dict:
    """Create and return a product tied to the generated_business fixture."""
    response = await client.post(
        "/api/v1/products",
        json={
            "business_id": generated_business["id"],
            "name": "Starter Kit",
            "description": "Everything you need to get started.",
            "price": "49.00",
            "currency": "usd",
            "category": "digital",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()
