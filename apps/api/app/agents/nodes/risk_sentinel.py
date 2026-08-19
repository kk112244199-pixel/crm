"""风险预警 Agent Node"""
from app.agents.state import CRMGraphState
from app.agents.llm_caller import call_llm_json
from app.agents.prompts import RISK_SENTINEL_SYSTEM


async def risk_sentinel_node(state: CRMGraphState, db) -> dict:
    text = state.get("canonical_text") or ""
    ctx = state.get("page_context") or {}

    user_msg = (
        f"当前商机背景（含健康度）：{ctx}\n\n"
        f"会议纪要：\n{text}"
    )
    try:
        result = await call_llm_json(db, "risk_sentinel", RISK_SENTINEL_SYSTEM, user_msg)
        return {"risk_sentinel": result}
    except Exception as e:
        return {
            "risk_sentinel": {"risk_flags": [], "health_deductions": {}, "summary": "", "evidence": []},
            "errors": (state.get("errors") or []) + [{"agent": "risk_sentinel", "error": str(e)}],
        }
