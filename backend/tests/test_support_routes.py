import pytest


@pytest.mark.anyio
async def test_resolve_conversation_requires_matching_business(client, auth_headers, generated_business):
    first_business_id = generated_business["id"]
    second_response = await client.post(
        "/api/v1/businesses/generate",
        json={"interests": "AI coaching", "target_audience": "small teams"},
        headers=auth_headers,
    )
    assert second_response.status_code == 201
    second_business_id = second_response.json()["id"]

    conversation_response = await client.post(
        f"/api/v1/support/{first_business_id}/conversations",
        json={"visitor_token": "visitor-ownership-test"},
    )
    assert conversation_response.status_code == 201
    conversation_id = conversation_response.json()["id"]

    wrong_business_response = await client.patch(
        f"/api/v1/support/{second_business_id}/conversations/{conversation_id}/resolve",
        headers=auth_headers,
    )
    assert wrong_business_response.status_code == 404

    correct_business_response = await client.patch(
        f"/api/v1/support/{first_business_id}/conversations/{conversation_id}/resolve",
        headers=auth_headers,
    )
    assert correct_business_response.status_code == 200
    assert correct_business_response.json()["status"] == "resolved"
