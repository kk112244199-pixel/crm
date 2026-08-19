"""商机研判 Agent Node"""
from app.agents.state import CRMGraphState
from app.agents.llm_caller import call_llm_json
from app.agents.prompts import OPPORTUNITY_JUDGE_SYSTEM


async def opportunity_judge_node(state: CRMGraphState, db) -> dict:
    text = state.get("canonical_text") or ""
    ctx = state.get("page_context") or {}

    user_msg = (
        f"当前商机背景：{ctx}\n\n"
        f"会议纪要：\n{text}"
    )
    try:
        result = await call_llm_json(db, "opportunity_judge", OPPORTUNITY_JUDGE_SYSTEM, user_msg)
        return {"opportunity_judge": result}
    except Exception as e:
        return {
            "opportunity_judge": {"error": str(e), "evidence": []},
            "errors": (state.get("errors") or []) + [{"agent": "opportunity_judge", "error": str(e)}],
        }
