"""
Writeback API — 闭环 A 核心路由
POST /activities/extract      → 触发 Orchestrator，返回 PendingAction
GET  /pending-actions/{id}    → 查看 Proposal
POST /pending-actions/{id}/confirm → AE 逐项确认 → 写入业务表 + RAG ingest
POST /pending-actions/{id}/reject  → 拒绝，仅保留 Activity 原始记录
GET  /pending-actions/        → 列表（可按 opp 过滤）
"""
from __future__ import annotations
import uuid, json
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.core.security.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.crm import (
    Activity, ActivityType, Opportunity, Contact, RoleInDeal,
)
from app.models.memory import PendingAction
from app.schemas.writeback import (
    ExtractRequest, ExtractResponse, WritebackProposal,
    PendingActionConfirmRequest, PendingActionRejectRequest,
    PendingActionResponse,
)
from app.agents.graphs.orchestrator import run_orchestrator
from app.services.rag.ingest import ingest_activity
from app.services.guard import guard_input, GuardViolation, audit_guard_block, http_detail

router = APIRouter(prefix="/activities", tags=["writeback"])
pa_router = APIRouter(prefix="/pending-actions", tags=["writeback"])


# ── POST /activities/extract ──────────────────────────────────────────────────

@router.post("/extract", response_model=ExtractResponse)
async def extract_activity(
    req: ExtractRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """触发 Orchestrator 分析纪要，生成 WritebackProposal 存入 PendingAction。"""
    # Guard
    try:
        safe_text = guard_input(req.canonical_text)
    except GuardViolation as e:
        await audit_guard_block(
            db, current_user,
            endpoint="activities.extract",
            violation=e,
            snippet=req.canonical_text,
            opportunity_id=req.opportunity_id,
        )
        raise HTTPException(status_code=400, detail=http_detail(e))

    # Verify opportunity exists
    opp = await db.get(Opportunity, req.opportunity_id)
    if not opp:
        raise HTTPException(404, "Opportunity not found")

    # Create / get Activity
    if req.activity_id:
        activity = await db.get(Activity, req.activity_id)
        if not activity:
            raise HTTPException(404, "Activity not found")
    else:
        activity = Activity(
            opportunity_id=req.opportunity_id,
            owner_id=current_user.id,
            activity_type=ActivityType.MEETING,
            subject=f"会议纪要 — {opp.name}",
            body=safe_text,
            canonical_text=safe_text,
        )
        db.add(activity)
        await db.flush()

    # Build page context
    page_context = {
        "opportunity_id": str(req.opportunity_id),
        "opportunity_name": opp.name,
        "stage": opp.stage,
        "health_score": opp.health_score,
        "health_status": opp.health_status,
        "amount": float(opp.amount) if opp.amount else None,
        "competitor": opp.competitor,
        "user_id": str(current_user.id),
        **req.page_context,
    }

    # Run orchestrator
    state = await run_orchestrator(
        canonical_text=safe_text,
        page_context=page_context,
        db=db,
    )

    synthesis = state.get("synthesis") or {}
    plan = state.get("plan")

    # Build proposal
    proposal = WritebackProposal(
        contact_updates=synthesis.get("contact_updates", []),
        new_contacts=synthesis.get("new_contacts", []),
        opportunity_updates=synthesis.get("opportunity_updates", {}),
        tasks=synthesis.get("tasks", []),
        risk_flags=synthesis.get("risk_flags", []),
        reasoning=synthesis.get("reasoning", ""),
        evidence=synthesis.get("evidence", []),
        stage_hint=synthesis.get("stage_hint"),
        structured_summary=synthesis.get("structured_summary"),
    )

    # Create PendingAction
    pending = PendingAction(
        opportunity_id=req.opportunity_id,
        created_by=current_user.id,
        level="L1",
        action_type="writeback_proposal",
        payload={
            "activity_id": str(activity.id),
            "proposal": proposal.model_dump(),
            "agents_activated": plan.get("agents", []) if plan else [],
            "plan_reasoning": plan.get("reasoning", "") if plan else "",
            "errors": state.get("errors", []),
        },
        status="pending",
    )
    db.add(pending)
    await db.commit()

    return ExtractResponse(
        pending_action_id=pending.id,
        proposal=proposal,
        agents_activated=plan.get("agents", []) if plan else [],
        plan_reasoning=plan.get("reasoning", "") if plan else "",
        errors=state.get("errors", []),
    )


# ── GET /pending-actions/ ─────────────────────────────────────────────────────

@pa_router.get("/", response_model=list[PendingActionResponse])
async def list_pending_actions(
    opportunity_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(PendingAction)
    if opportunity_id:
        q = q.where(PendingAction.opportunity_id == opportunity_id)
    if status:
        q = q.where(PendingAction.status == status)
    result = await db.execute(q.order_by(PendingAction.created_at.desc()).limit(50))
    return result.scalars().all()


# ── GET /pending-actions/{id} ─────────────────────────────────────────────────

@pa_router.get("/{pending_id}", response_model=PendingActionResponse)
async def get_pending_action(
    pending_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pa = await db.get(PendingAction, pending_id)
    if not pa:
        raise HTTPException(404, "PendingAction not found")
    return pa


# ── POST /pending-actions/{id}/confirm ───────────────────────────────────────

@pa_router.post("/{pending_id}/confirm", response_model=PendingActionResponse)
async def confirm_pending_action(
    pending_id: uuid.UUID,
    body: PendingActionConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AE 确认 Proposal → 写入 Contact / Opp / Activity，触发 RAG ingest。"""
    pa = await db.get(PendingAction, pending_id)
    if not pa:
        raise HTTPException(404, "PendingAction not found")
    if pa.status != "pending":
        raise HTTPException(400, f"PendingAction already {pa.status}")

    payload = pa.payload or {}
    proposal: dict = payload.get("proposal", {})

    # Build field-level acceptance map
    accepted = {item.field: item for item in body.items}

    # ── Write contact updates ─────────────────────────────────────────────────
    for cu in proposal.get("contact_updates", []):
        if not _field_accepted(accepted, f"contact_{cu.get('full_name')}", default=True):
            continue
        if cu.get("contact_id"):
            contact = await db.get(Contact, uuid.UUID(cu["contact_id"]))
            if contact:
                if cu.get("role_in_deal"):
                    try:
                        contact.role_in_deal = RoleInDeal(cu["role_in_deal"])
                    except ValueError:
                        pass
                if cu.get("influence_level"):
                    contact.influence_level = cu["influence_level"]

    # ── Write new contacts ────────────────────────────────────────────────────
    for nc in proposal.get("new_contacts", []):
        if not _field_accepted(accepted, f"new_contact_{nc.get('full_name')}", default=True):
            continue
        opp = await db.get(Opportunity, pa.opportunity_id)
        new_c = Contact(
            account_id=opp.account_id,
            full_name=nc.get("full_name", "未知"),
            title=nc.get("title"),
            role_in_deal=_safe_role(nc.get("role_in_deal")),
            influence_level=nc.get("influence_level", 1),
        )
        db.add(new_c)

    # ── Write opportunity updates ─────────────────────────────────────────────
    opp_updates: dict = proposal.get("opportunity_updates", {})
    opp = await db.get(Opportunity, pa.opportunity_id)
    if opp:
        _apply_opp_update(opp, opp_updates, accepted)

    # ── Write structured summary to Activity ─────────────────────────────────
    activity_id = payload.get("activity_id")
    if activity_id:
        activity = await db.get(Activity, uuid.UUID(activity_id))
        if activity:
            structured = proposal.get("structured_summary")
            if structured and _field_accepted(accepted, "structured_summary", default=True):
                # structured_summary is JSONB; store as dict
                activity.structured_summary = {"text": structured} if isinstance(structured, str) else structured
            await db.flush()

            # RAG ingest (async — use Celery in P3, direct for P2)
            canonical = activity.canonical_text or ""
            if canonical:
                await ingest_activity(
                    db,
                    opportunity_id=pa.opportunity_id,
                    activity_id=activity.id,
                    canonical_text=canonical,
                    metadata={"opportunity_id": str(pa.opportunity_id)},
                )

    # Update PendingAction status
    pa.status = "approved"
    pa.reviewed_by = current_user.id
    pa.review_note = body.note

    from app.services.audit import write_audit
    await write_audit(
        db, actor=current_user, action="pending_action.confirm",
        resource_type="pending_action", resource_id=pa.id,
        opportunity_id=pa.opportunity_id,
        detail={"items": [i.model_dump() for i in body.items], "note": body.note},
    )

    await db.commit()

    # Async health recalculation (fire-and-forget via Celery)
    try:
        from app.tasks.health_batch import run_single_health
        run_single_health.delay(str(pa.opportunity_id))
    except Exception:
        pass  # Celery optional; don't fail confirm if worker unavailable

    return pa


# ── POST /pending-actions/{id}/reject ────────────────────────────────────────

@pa_router.post("/{pending_id}/reject", response_model=PendingActionResponse)
async def reject_pending_action(
    pending_id: uuid.UUID,
    body: PendingActionRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """拒绝 — 不写业务表，保留 Activity 原始记录。"""
    pa = await db.get(PendingAction, pending_id)
    if not pa:
        raise HTTPException(404, "PendingAction not found")
    if pa.status != "pending":
        raise HTTPException(400, f"PendingAction already {pa.status}")

    pa.status = "rejected"
    pa.reviewed_by = current_user.id
    pa.review_note = body.note

    from app.services.audit import write_audit
    await write_audit(
        db, actor=current_user, action="pending_action.reject",
        resource_type="pending_action", resource_id=pa.id,
        opportunity_id=pa.opportunity_id,
        detail={"note": body.note},
    )

    await db.commit()
    return pa


# ── Helpers ───────────────────────────────────────────────────────────────────

def _field_accepted(
    accepted: dict,
    field: str,
    default: bool = True,
) -> bool:
    if field in accepted:
        return accepted[field].accepted
    return default


def _safe_role(value: str | None) -> RoleInDeal:
    try:
        return RoleInDeal(value or "UNKNOWN")
    except ValueError:
        return RoleInDeal.UNKNOWN


def _apply_opp_update(opp: Opportunity, updates: dict, accepted: dict) -> None:
    simple_fields = ["pain_points", "competitor", "budget_status"]
    for f in simple_fields:
        if f in updates and updates[f] and _field_accepted(accepted, f, default=True):
            setattr(opp, f, updates[f])

    if "amount_hint" in updates and updates["amount_hint"] and _field_accepted(accepted, "amount", default=False):
        try:
            opp.amount = float(updates["amount_hint"])
        except (TypeError, ValueError):
            pass

    if "close_date_hint" in updates and updates["close_date_hint"] and _field_accepted(accepted, "close_date", default=False):
        try:
            from datetime import date
            opp.expected_close_date = date.fromisoformat(updates["close_date_hint"])
        except ValueError:
            pass
