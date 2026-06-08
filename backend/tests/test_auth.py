"""Tests for authentication — signup, login, and protected routes."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": "new@example.com", "password": "securepass123", "full_name": "New User"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient):
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "dupe@example.com", "password": "securepass123"},
    )
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": "dupe@example.com", "password": "securepass456"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_signup_weak_password(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": "weak@example.com", "password": "short"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "login@example.com", "password": "securepass123"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "securepass123"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_bad_password(client: AsyncClient):
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "badpwd@example.com", "password": "securepass123"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "badpwd@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "noone@example.com", "password": "anything"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "testuser@example.com"
    assert data["full_name"] == "Test User"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_routes_require_auth(client: AsyncClient):
    """All protected routes should return 401 without a token."""
    routes = [
        ("POST", "/api/v1/businesses/generate", {"interests": "test"}),
        ("GET", "/api/v1/businesses", None),
        ("GET", "/api/v1/products", None),
    ]
    for method, path, body in routes:
        if method == "POST":
            response = await client.post(path, json=body)
        else:
            response = await client.request(method, path)
        assert response.status_code == 401, f"{method} {path} should require auth"


@pytest.mark.asyncio
async def test_public_routes_no_auth_required(client: AsyncClient):
    """Public routes should NOT return 401."""
    # Analytics tracking should work without auth
    response = await client.post(
        "/api/v1/analytics/track",
        json={
            "business_id": "00000000-0000-0000-0000-000000000001",
            "event_type": "visit",
        },
    )
    # Might fail for other reasons (no business), but NOT 401
    assert response.status_code != 401

    # Health check
    response = await client.get("/health")
    assert response.status_code == 200
