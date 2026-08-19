"""
MockOpenAI — 完全本地 mock，不发网络请求。
用于 CI 测试和 E2E 验证（无需 LLM Key）。
根据 system_prompt 关键词返回对应 Agent 的固定 JSON 输出。
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _MockMessage:
    content: str
    role: str = "assistant"


@dataclass
class _MockChoice:
    message: _MockMessage
    index: int = 0
    finish_reason: str = "stop"


@dataclass
class _MockResponse:
    choices: list[_MockChoice]
    model: str = "mock"
    id: str = "mock-resp"


class _MockCompletions:
    async def create(self, *, model: str, messages: list, **kwargs) -> _MockResponse:
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user = next((m["content"] for m in messages if m["role"] == "user"), "")
        content = _generate_mock_response(system, user)
        return _MockResponse(choices=[_MockChoice(message=_MockMessage(content=content))])


class _MockChat:
    def __init__(self):
        self.completions = _MockCompletions()


class MockOpenAI:
    """Drop-in AsyncOpenAI replacement for tests."""
    def __init__(self, **kwargs):
        self.chat = _MockChat()


# ── Response generators ───────────────────────────────────────────────────────

def _generate_mock_response(system: str, user: str) -> str:
    s = system.lower()
    if "检索改写" in system or "检索改写" in s:
        import re
        q = re.sub(r"[？?！!。，,]", " ", user).strip()
        return re.sub(r"\s+", " ", q) or user
    if "planner" in s:
        return json.dumps({
            "scene": "meeting_extract",
            "agents": ["customer_insight", "opportunity_judge", "risk_sentinel", "action_planner"],
            "reasoning": "Mock: 激活全部 Agent"
        }, ensure_ascii=False)
    elif "客户洞察" in s:
        return json.dumps({
            "contact_updates": [
                {"full_name": "王总", "title": "VP 工程", "role_in_deal": "TECHNICAL_BUYER",
                 "influence_level": 4, "notes": "支持我方方案", "is_new": False}
            ],
            "decision_chain_notes": "Mock 决策链分析",
            "evidence": [{"snippet": "王总确认", "field": "contact_updates"}]
        }, ensure_ascii=False)
    elif "商机研判" in s:
        return json.dumps({
            "pain_points": "Mock：产线数据孤岛，报工效率低",
            "competitor": "用友 U9",
            "budget_status": "confirmed",
            "amount_hint": 3800000,
            "close_date_hint": "2026-09-30",
            "stage_hint": "PROPOSAL",
            "objections": ["SAP 接口改造成本高"],
            "meddic_gaps": {"economic_buyer": None, "champion": None},
            "evidence": [{"snippet": "预算 380 万", "field": "amount_hint"}]
        }, ensure_ascii=False)
    elif "风险预警" in s:
        return json.dumps({
            "risk_flags": [
                {"rule": "H003", "description": "用友 U9 竞对进入", "severity": "MEDIUM"}
            ],
            "health_deductions": {"H003": -10},
            "summary": "Mock 风险评估：竞对介入风险中等",
            "evidence": [{"snippet": "用友 U9 在内部做了演示", "rule": "H003"}]
        }, ensure_ascii=False)
    elif "行动规划" in s:
        return json.dumps({
            "tasks": [
                {"title": "发送 POC 方案", "owner": "李明", "due_date": "2026-08-15",
                 "priority": "HIGH", "type": "SEND_PROPOSAL"}
            ],
            "follow_up_rhythm": "Mock：2 周内跟进",
            "commitments": ["8 月 15 日前发出 POC 方案"],
            "evidence": [{"snippet": "李明承诺 8 月 15 日前发出", "task_title": "发送 POC 方案"}]
        }, ensure_ascii=False)
    elif "汇总" in s:
        return json.dumps({
            "contact_updates": [
                {"full_name": "王总", "title": "VP 工程", "role_in_deal": "TECHNICAL_BUYER",
                 "influence_level": 4, "notes": "支持我方方案", "is_new": False}
            ],
            "new_contacts": [],
            "opportunity_updates": {
                "pain_points": "产线数据孤岛，报工效率低",
                "competitor": "用友 U9",
                "budget_status": "confirmed",
                "amount_hint": 3800000,
                "close_date_hint": "2026-09-30",
                "meddic_gaps": {}
            },
            "tasks": [
                {"title": "发送 POC 方案", "owner": "李明",
                 "due_date": "2026-08-15", "priority": "HIGH", "type": "SEND_PROPOSAL"}
            ],
            "risk_flags": [
                {"rule": "H003", "description": "用友 U9 竞对进入", "severity": "MEDIUM"}
            ],
            "reasoning": "Mock 汇总分析",
            "evidence": [{"agent": "opportunity_judge", "snippet": "预算 380 万", "field": "amount_hint"}],
            "stage_hint": "PROPOSAL",
            "structured_summary": "会议确认预算 380 万，Q3 决策，POC 方案待发送。"
        }, ensure_ascii=False)
    elif "销售助手" in system or "copilot" in s:
        return json.dumps({
            "answer": "根据纪要，王总确认预算 380 万，计划 Q3 决策。",
            "citations": [{"snippet": "王总确认预算 380 万", "activity_id": None, "date": "2026-08-01"}],
            "clarification_needed": None,
            "no_data": False,
        }, ensure_ascii=False)
    elif "邮件写作" in system:
        return json.dumps({
            "subject": "POC 方案跟进",
            "body": "王总您好，按约定发送 POC 方案跟进，请您方便时反馈评审时间。",
        }, ensure_ascii=False)
    else:
        return json.dumps({"result": "mock", "content": user[:100]}, ensure_ascii=False)
