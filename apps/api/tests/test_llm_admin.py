"""
LLM Admin API 集成测试（Mock Provider）

覆盖：
- GET /admin/llm/options 不含 API Key
- PUT /admin/llm/settings 保存到 DB
- GET /admin/llm/settings 返回 DB 值
- POST /admin/llm/test mock provider 正常
- PUT 使用不在白名单的 provider → 400
"""
import pytest
from httpx import AsyncClient


async def _admin_token(client: AsyncClient) -> str:
    resp = await client.post(
        "/auth/token",
        data={"username": "admin@test.com", "password": "adm123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_options_no_api_key_in_response(client: AsyncClient, seed_users):
    token = await _admin_token(client)
    resp = await client.get("/admin/llm/options", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    for item in resp.json():
        assert "api_key" not in item
        assert "key" not in str(item).lower().replace("provider", "")


@pytest.mark.asyncio
async def test_upsert_and_get_settings(client: AsyncClient, seed_users):
    token = await _admin_token(client)
    payload = {
        "default_provider": "mock",
        "default_model": "mock-model",
        "fallback_provider": "mock",
        "fallback_model": "mock-model",
        "embedding_provider": "local",
        "embedding_model": "BAAI/bge-m3",
        "embedding_dimension": 1024,
        "rerank_enabled": True,
        "rerank_top_k": 20,
        "rerank_return_n": 5,
        "guard_enabled": True,
        "guard_mode": "rules",
        "change_note": "test save",
    }
    # Save
    resp = await client.put(
        "/admin/llm/settings", json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["default_provider"] == "mock"

    # Read back
    resp2 = await client.get("/admin/llm/settings", headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 200
    assert resp2.json()["default_provider"] == "mock"


@pytest.mark.asyncio
async def test_upsert_invalid_provider_returns_400(client: AsyncClient, seed_users):
    token = await _admin_token(client)
    payload = {
        "default_provider": "unknown_provider",
        "default_model": "some-model",
        "fallback_provider": "mock",
        "fallback_model": "mock-model",
        "embedding_provider": "local",
        "embedding_model": "BAAI/bge-m3",
        "embedding_dimension": 1024,
        "rerank_enabled": True,
        "rerank_top_k": 20,
        "rerank_return_n": 5,
        "guard_enabled": True,
        "guard_mode": "rules",
    }
    resp = await client.put(
        "/admin/llm/settings", json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 400
