"""
健康度 API
GET /opportunities/{opp_id}/health   → 扣分明细 + 实时重算
POST /opportunities/{opp_id}/health/recalculate → 手动触发重算
GET /dashboard/risk-board            → Manager 团队风险看板
"""
from __future__ import annotations
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.core.security.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.crm import Opportunity, OppStage
from app.services.health.calculator import recalculate_opp_health

router = APIRouter(tags=["health"])
dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class RuleDetail(BaseModel):
    rule_id: str
    title: str
    description: str
    severity: str
    deduction: int


class HealthDetail(BaseModel):
    opportunity_id: uuid.UUID
    opportunity_name: str
    score: int
    status: str
    rules: list[RuleDetail]


class RiskBoardItem(BaseModel):
    opportunity_id: uuid.UUID
    opportunity_name: str
    account_name: str
    owner_name: str
    stage: str
    amount: Optional[float]
    health_score: Optional[int]
    health_status: Optional[str]
    top_rules: list[str]  # Top 3 rule IDs


class RiskBoardResponse(BaseModel):
    red: list[RiskBoardItem]
    yellow: list[RiskBoardItem]
    green: list[RiskBoardItem]
    total: int


# ── GET /opportunities/{opp_id}/health ───────────────────────────────────────

@router.get("/opportunities/{opp_id}/health", response_model=HealthDetail)
async def get_opp_health(
    opp_id: uuid.UUID,
    recalc: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opp = await db.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(404, "Opportunity not found")

    if recalc or opp.health_score is None:
        result = await recalculate_opp_health(db, opp_id)
    else:
        # Return from cached DB data
        deductions: dict = opp.health_deductions or {}
        result = {
            "opportunity_id": str(opp_id),
            "score": opp.health_score,
            "status": opp.health_status or "GREEN",
            "rules": [
                {
                    "rule_id": rid,
                    "title": v.get("title", rid),
                    "description": v.get("description", ""),
                    "severity": v.get("severity", "MEDIUM"),
                    "deduction": v.get("deduction", 0),
                }
                for rid, v in deductions.items()
            ],
        }

    return HealthDetail(
        opportunity_id=opp_id,
        opportunity_name=opp.name,
        score=result["score"],
        status=result["status"],
        rules=[RuleDetail(**r) for r in result.get("rules", [])],
    )


# ── POST /opportunities/{opp_id}/health/recalculate ─────────────────────────

@router.post("/opportunities/{opp_id}/health/recalculate", response_model=HealthDetail)
async def force_recalculate(
    opp_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opp = await db.get(Opportunity, opp_id)
    if not opp:
        raise HTTPException(404, "Opportunity not found")
    result = await recalculate_opp_health(db, opp_id)
    return HealthDetail(
        opportunity_id=opp_id,
        opportunity_name=opp.name,
        score=result["score"],
        status=result["status"],
        rules=[RuleDetail(**r) for r in result.get("rules", [])],
    )


# ── GET /dashboard/risk-board ────────────────────────────────────────────────

@dashboard_router.get("/risk-board", response_model=RiskBoardResponse)
async def risk_board(
    owner_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manager 风险看板：
    - MANAGER/ADMIN 可看全团队（或按 owner_id 过滤）
    - AE 只能看自己的
    """
    from app.models.crm import Account
    from app.models.user import User as UserModel
    from sqlalchemy.orm import aliased

    # Enforce visibility
    if current_user.role == UserRole.AE:
        filter_owner = current_user.id
    elif owner_id:
        filter_owner = owner_id
    else:
        filter_owner = None

    q = (
        select(Opportunity, Account.name.label("account_name"), UserModel.full_name.label("owner_name"))
        .join(Account, Opportunity.account_id == Account.id)
        .join(UserModel, Opportunity.owner_id == UserModel.id)
        .where(Opportunity.stage.notin_([OppStage.CLOSED_WON, OppStage.CLOSED_LOST]))
    )
    if filter_owner:
        q = q.where(Opportunity.owner_id == filter_owner)

    rows = (await db.execute(q)).all()

    def _to_item(opp: Opportunity, account_name: str, owner_name: str) -> RiskBoardItem:
        deductions: dict = opp.health_deductions or {}
        top_rules = list(deductions.keys())[:3]
        return RiskBoardItem(
            opportunity_id=opp.id,
            opportunity_name=opp.name,
            account_name=account_name,
            owner_name=owner_name,
            stage=opp.stage.value if hasattr(opp.stage, "value") else str(opp.stage),
            amount=float(opp.amount) if opp.amount else None,
            health_score=opp.health_score,
            health_status=opp.health_status.value if hasattr(opp.health_status, "value") else opp.health_status,
            top_rules=top_rules,
        )

    red, yellow, green = [], [], []
    for opp, acc_name, owner_name in rows:
        item = _to_item(opp, acc_name, owner_name)
        status = (opp.health_status.value if hasattr(opp.health_status, "value") else opp.health_status) or "GREEN"
        if status == "RED":
            red.append(item)
        elif status == "YELLOW":
            yellow.append(item)
        else:
            green.append(item)

    # Sort by score asc (worst first)
    red.sort(key=lambda x: x.health_score or 0)
    yellow.sort(key=lambda x: x.health_score or 0)

    return RiskBoardResponse(red=red, yellow=yellow, green=green, total=len(rows))
