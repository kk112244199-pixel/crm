"""行动规划 Agent Node"""
from app.agents.state import CRMGraphState
from app.agents.llm_caller import call_llm_json
from app.agents.prompts import ACTION_PLANNER_SYSTEM


async def action_planner_node(state: CRMGraphState, db) -> dict:
    text = state.get("canonical_text") or ""
    ctx = state.get("page_context") or {}
    stage_hint = (state.get("opportunity_judge") or {}).get("stage_hint")

    user_msg = (
        f"当前商机背景：{ctx}\n"
        f"商机阶段建议：{stage_hint}\n\n"
        f"会议纪要：\n{text}"
    )
    try:
        result = await call_llm_json(db, "action_planner", ACTION_PLANNER_SYSTEM, user_msg)
        return {"action_planner": result}
    except Exception as e:
        return {
            "action_planner": {"tasks": [], "commitments": [], "evidence": []},
            "errors": (state.get("errors") or []) + [{"agent": "action_planner", "error": str(e)}],
        }
