"""
Orchestrator Graph — 完整 LangGraph fan-out/fan-in 实现

拓扑：
    entry → planner → [fan_out] → 专责路由 → [join] → synthesizer → END

fan-out：根据 plan.agents 动态决定激活哪些路径
join：等待所有激活的专责 Agent 完成
HITL：在 synthesizer 后，API 层通过 /pending-actions 完成 interrupt
"""
from __future__ import annotations
import asyncio
from typing import Callable
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import CRMGraphState
from app.agents.nodes.planner import planner_node
from app.agents.nodes.customer_insight import customer_insight_node
from app.agents.nodes.opportunity_judge import opportunity_judge_node
from app.agents.nodes.risk_sentinel import risk_sentinel_node
from app.agents.nodes.action_planner import action_planner_node
from app.agents.nodes.synthesizer import synthesizer_node

# Node name → coroutine
_AGENT_REGISTRY: dict[str, Callable] = {
    "customer_insight": customer_insight_node,
    "opportunity_judge": opportunity_judge_node,
    "risk_sentinel": risk_sentinel_node,
    "action_planner": action_planner_node,
}

_TIMEOUT_MAP = {
    "customer_insight": 20,
    "opportunity_judge": 20,
    "risk_sentinel": 15,
    "action_planner": 10,
}


async def _run_agent_with_timeout(
    name: str,
    state: CRMGraphState,
    db: AsyncSession,
) -> dict:
    """单路专责 Agent，带超时保护。"""
    from app.core.tracing import agent_span
    fn = _AGENT_REGISTRY[name]
    timeout = _TIMEOUT_MAP.get(name, 20)
    with agent_span(name):
        try:
            return await asyncio.wait_for(fn(state, db), timeout=timeout)
        except asyncio.TimeoutError:
            return {
                "errors": (state.get("errors") or []) + [
                    {"agent": name, "error": f"TimeoutError after {timeout}s"}
                ]
            }


def _merge_state(base: CRMGraphState, *updates: dict) -> CRMGraphState:
    """合并多个 Agent 输出到共享 state。"""
    merged = dict(base)
    for u in updates:
        for k, v in u.items():
            if k == "errors":
                merged["errors"] = (merged.get("errors") or []) + v
            else:
                merged[k] = v
    return merged  # type: ignore[return-value]


async def run_orchestrator(
    canonical_text: str,
    page_context: dict,
    db: AsyncSession,
    thread_id: str | None = None,
) -> CRMGraphState:
    """
    完整编排入口：
    1. Planner 决定激活集合
    2. Fan-out：并行运行激活的专责 Agent（带超时）
    3. Fan-in：合并所有输出
    4. Synthesizer：生成 WritebackProposal
    返回最终 state（包含 synthesis）
    """
    import uuid
    from app.core.tracing import agent_trace, agent_span

    state: CRMGraphState = {
        "thread_id": thread_id or str(uuid.uuid4()),
        "scene": "meeting_extract",
        "page_context": page_context,
        "canonical_text": canonical_text,
        "raw_query": None,
        "plan": None,
        "customer_insight": None,
        "opportunity_judge": None,
        "risk_sentinel": None,
        "action_planner": None,
        "synthesis": None,
        "errors": [],
        "pending_action_id": None,
        "hitl_decision": None,
        "shared_retrieval": None,
    }

    user_id = str(page_context.get("user_id") or "")
    opp_id = str(page_context.get("opportunity_id") or "")

    with agent_trace(
        name="orchestrator",
        scene="meeting_extract",
        thread_id=state["thread_id"],
        user_id=user_id or None,
        opportunity_id=opp_id or None,
        tags=["meeting_extract"],
    ):
        with agent_span("planner", input_text=canonical_text):
            plan_update = await planner_node(state, db)
        state = _merge_state(state, plan_update)
        plan = state.get("plan")

        agents_to_run = plan.get("agents", []) if plan else []
        agents_to_run = [a for a in agents_to_run if a in _AGENT_REGISTRY]
        if not agents_to_run:
            agents_to_run = list(_AGENT_REGISTRY.keys())

        with agent_span("fan_out"):
            tasks = [_run_agent_with_timeout(name, state, db) for name in agents_to_run]
            results = await asyncio.gather(*tasks, return_exceptions=False)

        state = _merge_state(state, *results)

        with agent_span("synthesizer"):
            synth_update = await synthesizer_node(state, db)
        state = _merge_state(state, synth_update)

    return state
