"""客户洞察 Agent Node"""
from app.agents.state import CRMGraphState
from app.agents.llm_caller import call_llm_json
from app.agents.prompts import CUSTOMER_INSIGHT_SYSTEM


async def customer_insight_node(state: CRMGraphState, db) -> dict:
    text = state.get("canonical_text") or ""
    ctx = state.get("page_context") or {}

    user_msg = (
        f"当前商机背景：{ctx}\n\n"
        f"会议纪要：\n{text}"
    )
    try:
        result = await call_llm_json(db, "customer_insight", CUSTOMER_INSIGHT_SYSTEM, user_msg)
        return {"customer_insight": result}
    except Exception as e:
        return {
            "customer_insight": {"error": str(e), "contact_updates": [], "evidence": []},
            "errors": (state.get("errors") or []) + [{"agent": "customer_insight", "error": str(e)}],
        }
