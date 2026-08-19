"""汇总 Agent Node — 合并四路输出，生成 WritebackProposal"""
from __future__ import annotations
import json
from app.agents.state import CRMGraphState
from app.agents.llm_caller import call_llm_json
from app.agents.prompts import SYNTHESIZER_SYSTEM


def _build_context(state: CRMGraphState) -> str:
    parts = []
    if state.get("customer_insight"):
        parts.append(f"=== 客户洞察 Agent ===\n{json.dumps(state['customer_insight'], ensure_ascii=False, indent=2)}")
    if state.get("opportunity_judge"):
        parts.append(f"=== 商机研判 Agent ===\n{json.dumps(state['opportunity_judge'], ensure_ascii=False, indent=2)}")
    if state.get("risk_sentinel"):
        parts.append(f"=== 风险预警 Agent ===\n{json.dumps(state['risk_sentinel'], ensure_ascii=False, indent=2)}")
    if state.get("action_planner"):
        parts.append(f"=== 行动规划 Agent ===\n{json.dumps(state['action_planner'], ensure_ascii=False, indent=2)}")
    errors = state.get("errors") or []
    if errors:
        parts.append(f"=== 部分 Agent 失败（降级） ===\n{json.dumps(errors, ensure_ascii=False)}")
    return "\n\n".join(parts)


async def synthesizer_node(state: CRMGraphState, db) -> dict:
    context = _build_context(state)
    canonical = state.get("canonical_text") or ""

    user_msg = (
        f"原始纪要：\n{canonical}\n\n"
        f"各专责 Agent 分析结果：\n{context}\n\n"
        f"请合并以上结果，生成最终 WritebackProposal。"
    )
    try:
        result = await call_llm_json(db, "synth", SYNTHESIZER_SYSTEM, user_msg, max_tokens=3000)

        # Validate: evidence must exist
        if not result.get("evidence"):
            result["evidence"] = []

        # Add warning banner if agents had errors
        errors = state.get("errors") or []
        if errors:
            failed = ", ".join(e["agent"] for e in errors)
            result["reasoning"] = f"⚠ {failed} 暂不可用（已降级）\n" + result.get("reasoning", "")

        return {"synthesis": result}
    except Exception as e:
        return {
            "synthesis": {
                "reasoning": f"汇总失败: {e}",
                "evidence": [],
                "contact_updates": [],
                "opportunity_updates": {},
                "tasks": [],
                "risk_flags": [],
            },
            "errors": (state.get("errors") or []) + [{"agent": "synthesizer", "error": str(e)}],
        }
