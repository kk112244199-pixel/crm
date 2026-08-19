"""
CRMGraphState — LangGraph 共享状态（P2 实现 Orchestrator；P1 仅定义结构）

用法（P2）:
    from langgraph.graph import StateGraph
    graph = StateGraph(CRMGraphState)
"""
from __future__ import annotations
from typing import Any, TypedDict


class PageContext(TypedDict, total=False):
    account_id: str
    opportunity_id: str
    contact_ids: list[str]
    opp_stage: str
    recent_health_status: str


class AgentPlan(TypedDict, total=False):
    scene: str                        # meeting_extract | copilot_query | copilot_draft
    agents: list[str]                 # ["customer_insight", "opportunity_judge", ...]
    reasoning: str
    matched_account_id: str | None
    matched_opportunity_id: str | None


class CRMGraphState(TypedDict, total=False):
    # ── Input ────────────────────────────────────────────────────────────────
    thread_id: str
    scene: str
    page_context: PageContext
    canonical_text: str | None        # 预处理后纪要全文
    raw_query: str | None             # Copilot 原始问题

    # ── Planner output ───────────────────────────────────────────────────────
    plan: AgentPlan | None

    # ── Specialist Agent outputs ─────────────────────────────────────────────
    customer_insight: dict | None      # 客户洞察 Agent
    opportunity_judge: dict | None     # 商机研判 Agent
    risk_sentinel: dict | None         # 风险预警 Agent
    action_planner: dict | None        # 行动规划 Agent

    # ── Synthesizer output ───────────────────────────────────────────────────
    synthesis: dict | None             # WritebackProposal | CopilotAnswer
    errors: list[dict]                 # [{agent: "risk_sentinel", error: "TimeoutError"}]

    # ── HITL ─────────────────────────────────────────────────────────────────
    pending_action_id: str | None
    hitl_decision: str | None          # "approved" | "rejected"

    # ── Shared retrieval (P3 optional) ───────────────────────────────────────
    shared_retrieval: list[dict] | None
