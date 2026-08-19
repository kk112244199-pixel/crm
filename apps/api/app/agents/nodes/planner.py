"""Planner Agent Node — 识别场景，决定激活哪些专责 Agent"""
from __future__ import annotations
import yaml, pathlib
from app.agents.state import CRMGraphState, AgentPlan
from app.agents.llm_caller import call_llm_json
from app.agents.prompts import PLANNER_SYSTEM

_RULES_PATH = pathlib.Path(__file__).parents[4] / "config" / "planner_rules.yaml"


def _load_rules() -> dict:
    try:
        return yaml.safe_load(_RULES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _fallback_rule_based(text: str) -> list[str]:
    """纯规则激活，当 Planner LLM 失败时使用。"""
    rules = _load_rules().get("meeting_extract", {})
    agents = {"opportunity_judge"}  # always on

    lower = text.lower()
    kw_rules = rules.get("keyword_rules", {})

    # customer_insight
    ci_kw = kw_rules.get("customer_insight", {}).get("keywords", [])
    if len(text) > 200 or any(k in text for k in ci_kw):
        agents.add("customer_insight")

    # risk_sentinel
    rs_kw = kw_rules.get("risk_sentinel", {}).get("keywords", [])
    if kw_rules.get("risk_sentinel", {}).get("default") or any(k in text for k in rs_kw):
        agents.add("risk_sentinel")

    # action_planner
    ap_kw = kw_rules.get("action_planner", {}).get("keywords", [])
    if kw_rules.get("action_planner", {}).get("default") or any(k in text for k in ap_kw):
        agents.add("action_planner")

    return list(agents)


async def planner_node(state: CRMGraphState, db) -> dict:
    text = state.get("canonical_text") or ""

    if len(text.strip()) < 20:
        return {"plan": AgentPlan(
            scene="meeting_extract",
            agents=[],
            reasoning="纪要过短，跳过分析",
        )}

    user_msg = f"以下是销售会议纪要，请决定需要激活哪些 Agent：\n\n{text}"

    try:
        result = await call_llm_json(db, "planner", PLANNER_SYSTEM, user_msg, max_tokens=256)
        agents = result.get("agents", [])
        # Ensure opportunity_judge always on
        if "opportunity_judge" not in agents:
            agents.append("opportunity_judge")
        return {"plan": AgentPlan(
            scene=result.get("scene", "meeting_extract"),
            agents=agents,
            reasoning=result.get("reasoning", ""),
        )}
    except Exception as e:
        # Fallback to rule-based
        agents = _fallback_rule_based(text)
        return {"plan": AgentPlan(
            scene="meeting_extract",
            agents=agents,
            reasoning=f"Planner LLM 失败，使用规则引擎: {e}",
        )}
