"""
从数据库构建 HealthContext 并计算健康度
"""
from __future__ import annotations
import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case

from app.models.crm import Opportunity, Activity, Contact, ActivityType, RoleInDeal
from app.services.health.rules import HealthContext, RuleResult, evaluate_health


_HIGH_LEVEL_TITLES = {"CEO", "CFO", "CTO", "总裁", "副总裁", "董事长", "VP"}
_HIGH_LEVEL_ROLES = {RoleInDeal.ECONOMIC_BUYER}


async def build_context(db: AsyncSession, opp: Opportunity) -> HealthContext:
    """Query DB once and build HealthContext."""
    # Last activity date
    act_q = (
        select(func.max(Activity.created_at))
        .where(Activity.opportunity_id == opp.id)
    )
    last_act_dt = (await db.execute(act_q)).scalar_one_or_none()
    last_activity_date = last_act_dt.date() if last_act_dt else None

    # Contacts: has economic buyer?  last high-level contact?
    contacts_q = select(Contact).where(Contact.account_id == opp.account_id)
    contacts = (await db.execute(contacts_q)).scalars().all()

    has_economic_buyer = any(
        c.role_in_deal == RoleInDeal.ECONOMIC_BUYER for c in contacts
    )

    high_level_ids = [
        c.id for c in contacts
        if c.role_in_deal in _HIGH_LEVEL_ROLES
        or any(t in (c.title or "") for t in _HIGH_LEVEL_TITLES)
    ]

    last_hl_date: date | None = None
    if high_level_ids:
        # Activities mentioning high-level contacts (activity body heuristic)
        hl_act_q = (
            select(func.max(Activity.created_at))
            .where(Activity.opportunity_id == opp.id)
            .where(Activity.activity_type.in_([ActivityType.MEETING, ActivityType.CALL]))
        )
        hl_dt = (await db.execute(hl_act_q)).scalar_one_or_none()
        last_hl_date = hl_dt.date() if hl_dt else None

    return HealthContext(
        opp_id=opp.id,
        opp_name=opp.name,
        stage=opp.stage.value if hasattr(opp.stage, "value") else str(opp.stage),
        amount=float(opp.amount) if opp.amount else None,
        expected_close_date=opp.expected_close_date,
        competitor=opp.competitor,
        budget_status=opp.budget_status,
        meddic_gaps=opp.meddic_gaps or {},
        last_activity_date=last_activity_date,
        last_high_level_contact_date=last_hl_date,
        has_economic_buyer_confirmed=has_economic_buyer,
        total_activities=0,
    )


async def recalculate_opp_health(db: AsyncSession, opp_id: uuid.UUID) -> dict:
    """
    Recalculate health for one opportunity and persist to DB.
    Returns {"score": int, "status": str, "rules": [...]}
    """
    opp = await db.get(Opportunity, opp_id)
    if not opp:
        return {}

    ctx = await build_context(db, opp)
    score, status, triggered = evaluate_health(ctx)

    # Persist
    prev = opp.health_status.value if hasattr(opp.health_status, "value") else str(opp.health_status or "")
    opp.health_score = score
    opp.health_status = status  # type: ignore[assignment]
    opp.health_deductions = {
        r.rule_id: {
            "title": r.title,
            "description": r.description,
            "severity": r.severity,
            "deduction": r.deduction,
            "evidence": r.evidence,
        }
        for r in triggered
    }
    await db.commit()

    if prev != "RED" and status == "RED":
        try:
            from app.services.dingtalk import enqueue_dingtalk
            rules = "；".join(f"{r.rule_id} {r.title}" for r in triggered[:6]) or "—"
            enqueue_dingtalk("opp_red", {
                "opportunity_id": str(opp_id),
                "opp_name": opp.name,
                "score": score,
                "rules": rules,
                "suggestion": "请尽快跟进决策链与竞对，避免丢单。",
            })
        except Exception:
            pass

    return {
        "opportunity_id": str(opp_id),
        "score": score,
        "status": status,
        "rules": [
            {
                "rule_id": r.rule_id,
                "title": r.title,
                "description": r.description,
                "severity": r.severity,
                "deduction": r.deduction,
            }
            for r in triggered
        ],
    }
