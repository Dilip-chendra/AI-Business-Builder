import pytest


@pytest.mark.anyio
async def test_generate_campaign_image_uses_real_usage_service_and_persists_url(
    client,
    auth_headers,
    generated_business,
    monkeypatch,
):
    campaign_response = await client.post(
        f"/api/v1/marketing/{generated_business['id']}/campaigns/social",
        json={"platform": "linkedin", "post_count": 1},
        headers=auth_headers,
    )
    assert campaign_response.status_code == 201
    campaign = campaign_response.json()

    async def fake_generate(self, *, prompt, size, brand=None):
        assert generated_business["name"] in prompt
        return "/uploads/test-campaign-image.png"

    monkeypatch.setattr(
        "app.services.image_generation_service.ImageGenerationService.generate",
        fake_generate,
    )

    image_response = await client.post(
        f"/api/v1/marketing/{generated_business['id']}/campaigns/{campaign['id']}/generate-image",
        headers=auth_headers,
    )

    assert image_response.status_code == 200
    assert image_response.json()["image_url"] == "/uploads/test-campaign-image.png"

    list_response = await client.get(
        f"/api/v1/marketing/{generated_business['id']}/campaigns",
        headers=auth_headers,
    )
    assert list_response.status_code == 200
    [saved_campaign] = list_response.json()
    assert saved_campaign["image_url"] == "/uploads/test-campaign-image.png"


@pytest.mark.anyio
async def test_campaign_approval_requires_matching_business_and_persists_state(
    client,
    auth_headers,
    generated_business,
):
    other_business_response = await client.post(
        "/api/v1/businesses/generate",
        json={"interests": "home services", "target_audience": "homeowners"},
        headers=auth_headers,
    )
    assert other_business_response.status_code == 201
    other_business = other_business_response.json()

    campaign_response = await client.post(
        f"/api/v1/marketing/{generated_business['id']}/campaigns/social",
        json={"platform": "linkedin", "post_count": 1},
        headers=auth_headers,
    )
    assert campaign_response.status_code == 201
    campaign = campaign_response.json()

    wrong_business_response = await client.post(
        f"/api/v1/marketing/{other_business['id']}/campaigns/{campaign['id']}/approve",
        headers=auth_headers,
    )
    assert wrong_business_response.status_code == 404

    approve_response = await client.post(
        f"/api/v1/marketing/{generated_business['id']}/campaigns/{campaign['id']}/approve",
        headers=auth_headers,
    )
    assert approve_response.status_code == 200
    approved = approve_response.json()
    assert approved["status"] == "approved"
    assert approved["lifecycle_status"] == "approved"

    detail_response = await client.get(
        f"/api/v1/marketing/{generated_business['id']}/campaigns/{campaign['id']}",
        headers=auth_headers,
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "approved"


@pytest.mark.anyio
async def test_publish_requires_approval_and_matching_business(
    client,
    auth_headers,
    generated_business,
):
    other_business_response = await client.post(
        "/api/v1/businesses/generate",
        json={"interests": "local services", "target_audience": "homeowners"},
        headers=auth_headers,
    )
    assert other_business_response.status_code == 201
    other_business = other_business_response.json()

    campaign_response = await client.post(
        f"/api/v1/marketing/{generated_business['id']}/campaigns/social",
        json={"platform": "linkedin", "post_count": 1},
        headers=auth_headers,
    )
    assert campaign_response.status_code == 201
    campaign = campaign_response.json()

    unapproved_response = await client.post(
        f"/api/v1/marketing/{generated_business['id']}/campaigns/{campaign['id']}/publish/linkedin",
        headers=auth_headers,
    )
    assert unapproved_response.status_code == 400
    assert "Approve this campaign" in unapproved_response.json()["detail"]

    wrong_business_response = await client.post(
        f"/api/v1/marketing/{other_business['id']}/campaigns/{campaign['id']}/publish/linkedin",
        headers=auth_headers,
    )
    assert wrong_business_response.status_code == 404


@pytest.mark.anyio
async def test_schedule_requires_approval_and_matching_business(
    client,
    auth_headers,
    generated_business,
):
    other_business_response = await client.post(
        "/api/v1/businesses/generate",
        json={"interests": "local services", "target_audience": "homeowners"},
        headers=auth_headers,
    )
    assert other_business_response.status_code == 201
    other_business = other_business_response.json()

    campaign_response = await client.post(
        f"/api/v1/marketing/{generated_business['id']}/campaigns/social",
        json={"platform": "linkedin", "post_count": 1},
        headers=auth_headers,
    )
    assert campaign_response.status_code == 201
    campaign = campaign_response.json()
    schedule_payload = {
        "scheduled_at": "2026-06-08T16:00:00+05:30",
        "timezone": "Asia/Calcutta",
        "platform": "linkedin",
    }

    unapproved_response = await client.post(
        f"/api/v1/marketing/{generated_business['id']}/campaigns/{campaign['id']}/schedule",
        json=schedule_payload,
        headers=auth_headers,
    )
    assert unapproved_response.status_code == 400
    assert "Approve this campaign" in unapproved_response.json()["detail"]

    wrong_business_response = await client.post(
        f"/api/v1/marketing/{other_business['id']}/campaigns/{campaign['id']}/schedule",
        json=schedule_payload,
        headers=auth_headers,
    )
    assert wrong_business_response.status_code == 404

    approve_response = await client.post(
        f"/api/v1/marketing/{generated_business['id']}/campaigns/{campaign['id']}/approve",
        headers=auth_headers,
    )
    assert approve_response.status_code == 200

    schedule_response = await client.post(
        f"/api/v1/marketing/{generated_business['id']}/campaigns/{campaign['id']}/schedule",
        json=schedule_payload,
        headers=auth_headers,
    )
    assert schedule_response.status_code == 200
    assert schedule_response.json()["status"] == "pending"

    detail_response = await client.get(
        f"/api/v1/marketing/{generated_business['id']}/campaigns/{campaign['id']}",
        headers=auth_headers,
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "scheduled"
    assert detail["lifecycle_status"] == "scheduled"


@pytest.mark.anyio
async def test_reject_duplicate_and_ab_test_require_matching_business(
    client,
    auth_headers,
    generated_business,
):
    other_business_response = await client.post(
        "/api/v1/businesses/generate",
        json={"interests": "local services", "target_audience": "homeowners"},
        headers=auth_headers,
    )
    assert other_business_response.status_code == 201
    other_business = other_business_response.json()

    campaign_response = await client.post(
        f"/api/v1/marketing/{generated_business['id']}/campaigns/social",
        json={"platform": "linkedin", "post_count": 1},
        headers=auth_headers,
    )
    assert campaign_response.status_code == 201
    campaign = campaign_response.json()

    reject_response = await client.post(
        f"/api/v1/marketing/{other_business['id']}/campaigns/{campaign['id']}/reject",
        json={"reason": "Not the right campaign for this business."},
        headers=auth_headers,
    )
    assert reject_response.status_code == 404

    duplicate_response = await client.post(
        f"/api/v1/marketing/{other_business['id']}/campaigns/{campaign['id']}/duplicate",
        headers=auth_headers,
    )
    assert duplicate_response.status_code == 404

    ab_test_response = await client.post(
        f"/api/v1/marketing/{other_business['id']}/campaigns/{campaign['id']}/ab-test",
        headers=auth_headers,
    )
    assert ab_test_response.status_code == 404


@pytest.mark.anyio
async def test_email_send_does_not_mark_sent_when_provider_rejects_all(
    client,
    auth_headers,
    generated_business,
    monkeypatch,
):
    campaign_response = await client.post(
        f"/api/v1/marketing/{generated_business['id']}/campaigns/email",
        json={"name": "Honest Send Test", "goal": "Invite customers", "recipient_count": 1},
        headers=auth_headers,
    )
    assert campaign_response.status_code == 201
    campaign = campaign_response.json()

    approve_response = await client.post(
        f"/api/v1/marketing/{generated_business['id']}/campaigns/{campaign['id']}/approve",
        headers=auth_headers,
    )
    assert approve_response.status_code == 200

    async def fake_send_marketing_campaign(self, user_id, to, subject, html_body, db):
        return False

    monkeypatch.setattr(
        "app.services.email_service.EmailService.send_marketing_campaign",
        fake_send_marketing_campaign,
    )

    send_response = await client.post(
        f"/api/v1/marketing/{generated_business['id']}/campaigns/{campaign['id']}/send",
        json={"recipient_emails": ["real.customer@example.com"]},
        headers=auth_headers,
    )
    assert send_response.status_code == 400
    assert "did not send any recipients" in send_response.json()["detail"]

    detail_response = await client.get(
        f"/api/v1/marketing/{generated_business['id']}/campaigns/{campaign['id']}",
        headers=auth_headers,
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "approved"
    assert detail["lifecycle_status"] == "approved"
