"""
Opportunity CRUD — with stage-advance validation + amount L2 approval
"""
import uuid
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.security.deps import CurrentUser, RequireAE, get_current_user
from app.models.crm import Opportunity, OppStage
from app.models.user import User, UserRole
from app.schemas.crm import OpportunityCreate, OpportunityUpdate, OpportunityOut

router = APIRouter(prefix="/opportunities", tags=["Opportunities"])

# Stage advance order
_STAGE_ORDER = [
    OppStage.PROSPECTING,
    OppStage.QUALIFICATION,
    OppStage.NEEDS_ANALYSIS,
    OppStage.VALUE_PROPOSITION,
    OppStage.PROPOSAL,
    OppStage.NEGOTIATION,
    OppStage.CLOSED_WON,
    OppStage.CLOSED_LOST,
]

# Required fields when entering a stage
_STAGE_REQUIRED: dict[OppStage, list[str]] = {
    OppStage.PROPOSAL:     ["amount", "expected_close_date"],
    OppStage.NEGOTIATION:  ["amount", "expected_close_date", "pain_points"],
    OppStage.CLOSED_WON:   ["amount", "expected_close_date"],
    OppStage.CLOSED_LOST:  [],
}

# Amount change threshold requiring L2 (Manager approval) — 20% change or >50万
_AMOUNT_L2_THRESHOLD_PCT = 0.20
_AMOUNT_L2_THRESHOLD_ABS = 500_000


def _stage_index(stage) -> int:
    try:
        s = OppStage(stage) if isinstance(stage, str) else stage
        return _STAGE_ORDER.index(s)
    except (ValueError, AttributeError):
        return -1


def _check_stage_advance(opp: Opportunity, new_stage: OppStage) -> list[str]:
    """Return list of missing required fields for stage advance."""
    required = _STAGE_REQUIRED.get(new_stage, [])
    missing = []
    for field in required:
        val = getattr(opp, field, None)
        if val is None:
            missing.append(field)
    return missing


def _needs_amount_approval(old_amount: Optional[float], new_amount: float) -> bool:
    if old_amount is None:
        return False
    pct_change = abs(new_amount - old_amount) / max(old_amount, 1)
    abs_change = abs(new_amount - old_amount)
    return pct_change >= _AMOUNT_L2_THRESHOLD_PCT and abs_change >= _AMOUNT_L2_THRESHOLD_ABS


@router.get("", response_model=list[OpportunityOut])
async def list_opportunities(
    _: Annotated[None, RequireAE],
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # AE sees own; MANAGER/ADMIN sees all
    q = select(Opportunity).order_by(Opportunity.created_at.desc())
    if current_user.role == UserRole.AE:
        q = q.where(Opportunity.owner_id == current_user.id)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("", response_model=OpportunityOut, status_code=status.HTTP_201_CREATED)
async def create_opportunity(
    body: OpportunityCreate,
    _: Annotated[None, RequireAE],
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    opp = Opportunity(**body.model_dump(), owner_id=current_user.id)
    db.add(opp)
    await db.commit()
    await db.refresh(opp)
    return opp


@router.get("/{opp_id}", response_model=OpportunityOut)
async def get_opportunity(
    opp_id: uuid.UUID,
    _: Annotated[None, RequireAE],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Opportunity).where(Opportunity.id == opp_id))
    opp = result.scalar_one_or_none()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return opp


@router.patch("/{opp_id}", response_model=OpportunityOut)
async def update_opportunity(
    opp_id: uuid.UUID,
    body: OpportunityUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Opportunity).where(Opportunity.id == opp_id))
    opp = result.scalar_one_or_none()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    updates = body.model_dump(exclude_none=True)

    # ── Stage advance validation ──────────────────────────────────────────────
    if "stage" in updates:
        new_stage = OppStage(updates["stage"]) if isinstance(updates["stage"], str) else updates["stage"]
        old_idx = _stage_index(opp.stage)
        new_idx = _stage_index(new_stage)
        if new_idx > old_idx:
            # Merge pending updates into opp for validation
            temp_opp = type("TempOpp", (), {
                k: updates.get(k, getattr(opp, k, None))
                for k in ["amount", "expected_close_date", "pain_points"]
            })()
            missing = _check_stage_advance(temp_opp, new_stage)  # type: ignore[arg-type]
            if missing:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "STAGE_ADVANCE_MISSING_FIELDS",
                        "message": f"推进到 {new_stage.value} 阶段需要填写：{', '.join(missing)}",
                        "missing_fields": missing,
                    },
                )

        # Audit stage change
        from app.services.audit import write_audit
        await write_audit(
            db, actor=current_user, action="opportunity.stage_change",
            resource_type="opportunity", resource_id=opp.id,
            opportunity_id=opp.id,
            detail={"from": str(opp.stage), "to": str(new_stage)},
        )

    # ── Amount L2 approval check ──────────────────────────────────────────────
    if "amount" in updates and updates["amount"] is not None:
        new_amount = float(updates["amount"])
        old_amount = float(opp.amount) if opp.amount else None
        if _needs_amount_approval(old_amount, new_amount) and current_user.role == UserRole.AE:
            # Create a PendingAction L2 instead of applying directly
            from app.models.memory import PendingAction
            pa = PendingAction(
                opportunity_id=opp.id,
                created_by=current_user.id,
                level="L2",
                action_type="amount_change",
                payload={
                    "old_amount": old_amount,
                    "new_amount": new_amount,
                    "requested_by": str(current_user.id),
                },
                status="pending",
            )
            db.add(pa)
            # Remove amount from this update — apply only after Manager approves
            del updates["amount"]

            from app.services.audit import write_audit
            await write_audit(
                db, actor=current_user, action="opportunity.amount_change_pending",
                resource_type="pending_action",
                opportunity_id=opp.id,
                detail={"old": old_amount, "new": new_amount},
            )
            await db.commit()
            try:
                from app.services.dingtalk import enqueue_dingtalk
                enqueue_dingtalk("pending_l2", {
                    "opportunity_id": str(opp.id),
                    "opp_name": opp.name,
                    "old_amount": old_amount,
                    "new_amount": new_amount,
                    "pending_action_id": str(pa.id),
                })
            except Exception:
                pass
            # Refresh and return current state (amount not changed yet)
            await db.refresh(opp)
            # Attach warning header
            raise HTTPException(
                status_code=202,
                detail={
                    "code": "AMOUNT_CHANGE_PENDING_APPROVAL",
                    "message": f"金额变更幅度较大，已提交主管审批（L2）。其他字段已更新。",
                    "pending_action_id": str(pa.id),
                },
            )

    # Apply remaining updates
    for k, v in updates.items():
        setattr(opp, k, v)

    await db.commit()
    await db.refresh(opp)
    return opp


@router.delete("/{opp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_opportunity(
    opp_id: uuid.UUID,
    _: Annotated[None, RequireAE],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Opportunity).where(Opportunity.id == opp_id))
    opp = result.scalar_one_or_none()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    await db.delete(opp)
    await db.commit()
