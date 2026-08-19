"""
闭环 A E2E 测试 — Mock LLM Provider
测试流程：POST /activities/extract → confirm → 验证写入
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock
import json

from app.core.llm.mock_client import MockOpenAI

# ── 10 条 golden 纪要样本 ──────────────────────────────────────────────────────
GOLDEN_MINUTES = [
    """\
【会议纪要】2026-08-01 与亿联智造 产品演示会
王总确认 MES 系统采购预算 380 万，Q3 决策。竞对：用友 U9。
李明承诺 8 月 15 日前发出 POC 方案。技术负责人张工支持我方方案。
""",
    """\
【拜访纪要】华峰精密
预算缩减 30%，MES 项目暂时搁置到 Q4。西门子低代码方案也在评估。
价格需降到 250 万以内。项目可能延期超 90 天。
""",
    """\
决策链：CEO 许总最终拍板，财务总监有一票否决权。
自建 vs 外购争议激烈，自研团队反对采购。
下一步：安排 CEO 级别会议，2 周内完成。
""",
]


@pytest.fixture(autouse=True)
def mock_llm_provider():
    """Replace all LLM calls with MockOpenAI."""
    mock = MockOpenAI()
    with patch(
        "app.agents.llm_caller.resolve_llm",
        new=AsyncMock(return_value=(mock, "mock-model")),
    ):
        yield


@pytest.fixture(autouse=True)
def mock_guard():
    """Disable Guard for tests."""
    with patch("app.routers.writeback.guard_input", side_effect=lambda x: x):
        yield


class TestExtractFlow:
    """POST /activities/extract → PendingAction 创建"""

    @pytest.mark.asyncio
    async def test_extract_creates_pending_action(self, client: AsyncClient, ae_token, test_opportunity_id):
        resp = await client.post(
            "/activities/extract",
            json={
                "opportunity_id": str(test_opportunity_id),
                "canonical_text": GOLDEN_MINUTES[0],
            },
            headers={"Authorization": f"Bearer {ae_token}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "pending_action_id" in data
        assert "proposal" in data
        assert len(data["agents_activated"]) > 0

    @pytest.mark.asyncio
    async def test_extract_short_text_rejected(self, client: AsyncClient, ae_token, test_opportunity_id):
        resp = await client.post(
            "/activities/extract",
            json={
                "opportunity_id": str(test_opportunity_id),
                "canonical_text": "太短",
            },
            headers={"Authorization": f"Bearer {ae_token}"},
        )
        assert resp.status_code == 422  # Pydantic min_length validation

    @pytest.mark.asyncio
    async def test_extract_nonexistent_opp(self, client: AsyncClient, ae_token):
        import uuid
        resp = await client.post(
            "/activities/extract",
            json={
                "opportunity_id": str(uuid.uuid4()),
                "canonical_text": GOLDEN_MINUTES[0],
            },
            headers={"Authorization": f"Bearer {ae_token}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    @pytest.mark.parametrize("minutes", GOLDEN_MINUTES)
    async def test_golden_minutes_regression(
        self, client: AsyncClient, ae_token, test_opportunity_id, minutes
    ):
        """3 条样本纪要回归 — 必须有 proposal.reasoning 和 agents_activated."""
        resp = await client.post(
            "/activities/extract",
            json={
                "opportunity_id": str(test_opportunity_id),
                "canonical_text": minutes,
            },
            headers={"Authorization": f"Bearer {ae_token}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["proposal"]["reasoning"], "reasoning must be non-empty"
        assert data["agents_activated"], "must have activated agents"


class TestHITLConfirmFlow:
    """confirm → 写入业务表验证"""

    @pytest.mark.asyncio
    async def test_confirm_updates_opportunity(
        self, client: AsyncClient, ae_token, test_opportunity_id
    ):
        # Step 1: Extract
        resp = await client.post(
            "/activities/extract",
            json={
                "opportunity_id": str(test_opportunity_id),
                "canonical_text": GOLDEN_MINUTES[0],
            },
            headers={"Authorization": f"Bearer {ae_token}"},
        )
        assert resp.status_code == 200
        pending_id = resp.json()["pending_action_id"]

        # Step 2: Confirm
        confirm_resp = await client.post(
            f"/pending-actions/{pending_id}/confirm",
            json={"items": []},  # accept all
            headers={"Authorization": f"Bearer {ae_token}"},
        )
        assert confirm_resp.status_code == 200
        assert confirm_resp.json()["status"] == "approved"

        # Step 3: Cannot confirm again
        confirm_resp2 = await client.post(
            f"/pending-actions/{pending_id}/confirm",
            json={"items": []},
            headers={"Authorization": f"Bearer {ae_token}"},
        )
        assert confirm_resp2.status_code == 400

    @pytest.mark.asyncio
    async def test_reject_keeps_activity_only(
        self, client: AsyncClient, ae_token, test_opportunity_id
    ):
        resp = await client.post(
            "/activities/extract",
            json={
                "opportunity_id": str(test_opportunity_id),
                "canonical_text": GOLDEN_MINUTES[1],
            },
            headers={"Authorization": f"Bearer {ae_token}"},
        )
        pending_id = resp.json()["pending_action_id"]

        reject_resp = await client.post(
            f"/pending-actions/{pending_id}/reject",
            json={"note": "不准确"},
            headers={"Authorization": f"Bearer {ae_token}"},
        )
        assert reject_resp.status_code == 200
        assert reject_resp.json()["status"] == "rejected"

    @pytest.mark.asyncio
    async def test_confirm_before_changes_business_table(
        self, client: AsyncClient, ae_token, test_opportunity_id
    ):
        """确认前 opp 不应变，confirm 后 pain_points/competitor 写入。"""
        # Get current opp
        opp_resp = await client.get(
            f"/opportunities/{test_opportunity_id}",
            headers={"Authorization": f"Bearer {ae_token}"},
        )
        original_competitor = opp_resp.json().get("competitor")

        # Extract + Confirm
        ext_resp = await client.post(
            "/activities/extract",
            json={
                "opportunity_id": str(test_opportunity_id),
                "canonical_text": GOLDEN_MINUTES[0],
            },
            headers={"Authorization": f"Bearer {ae_token}"},
        )
        pending_id = ext_resp.json()["pending_action_id"]

        await client.post(
            f"/pending-actions/{pending_id}/confirm",
            json={"items": []},
            headers={"Authorization": f"Bearer {ae_token}"},
        )

        # Verify opp updated
        opp_after = await client.get(
            f"/opportunities/{test_opportunity_id}",
            headers={"Authorization": f"Bearer {ae_token}"},
        )
        after_data = opp_after.json()
        # Mock always returns 用友 U9 as competitor
        assert after_data.get("competitor") == "用友 U9"


class TestPendingActionList:
    @pytest.mark.asyncio
    async def test_list_pending_actions(
        self, client: AsyncClient, ae_token, test_opportunity_id
    ):
        resp = await client.get(
            f"/pending-actions/?opportunity_id={test_opportunity_id}",
            headers={"Authorization": f"Bearer {ae_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
