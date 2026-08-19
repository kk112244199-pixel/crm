"""
CRUD smoke tests — 验证 Account / Contact / Opportunity / Activity 基本流程
"""
import pytest
from httpx import AsyncClient


async def _ae_token(client: AsyncClient) -> str:
    resp = await client.post(
        "/auth/token",
        data={"username": "ae@test.com", "password": "ae123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_account_crud(client: AsyncClient, seed_users):
    token = await _ae_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Create
    resp = await client.post("/accounts", json={"name": "Test Corp", "industry": "Manufacturing"}, headers=headers)
    assert resp.status_code == 201
    acc_id = resp.json()["id"]

    # Read
    resp = await client.get(f"/accounts/{acc_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Corp"

    # Update
    resp = await client.patch(f"/accounts/{acc_id}", json={"region": "华东"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["region"] == "华东"

    # List
    resp = await client.get("/accounts", headers=headers)
    assert any(a["id"] == acc_id for a in resp.json())

    # Delete
    resp = await client.delete(f"/accounts/{acc_id}", headers=headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_opportunity_crud(client: AsyncClient, seed_users):
    token = await _ae_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Need an account first
    acc_resp = await client.post("/accounts", json={"name": "Opp Corp"}, headers=headers)
    acc_id = acc_resp.json()["id"]

    # Create opportunity
    resp = await client.post(
        "/opportunities",
        json={"account_id": acc_id, "name": "Q1 Deal", "stage": "QUALIFICATION"},
        headers=headers,
    )
    assert resp.status_code == 201
    opp_id = resp.json()["id"]
    assert resp.json()["stage"] == "QUALIFICATION"

    # Update
    resp = await client.patch(f"/opportunities/{opp_id}", json={"pain_points": "Integration cost"}, headers=headers)
    assert resp.status_code == 200

    # Delete
    await client.delete(f"/opportunities/{opp_id}", headers=headers)
    await client.delete(f"/accounts/{acc_id}", headers=headers)
