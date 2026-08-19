"""
Copilot API — 闭环 C
POST /copilot/query   → RAG + LLM 问答（带 citations）
POST /copilot/draft   → 邮件草稿 → PendingAction L2
POST /copilot/draft/{id}/send → confirm 发送（MailHog MVP）
"""
from __future__ import annotations
import uuid
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.core.security.deps import get_current_user
from app.models.user import User
from app.models.crm import Opportunity
from app.models.memory import PendingAction
from app.services.rag.retriever import search_memory
from app.agents.llm_caller import call_llm_json
from app.agents.prompts import COPILOT_QUERY_SYSTEM, COPILOT_DRAFT_SYSTEM
from app.services.guard import (
    guard_input, guard_output, GuardViolation, audit_guard_block, http_detail,
)

router = APIRouter(prefix="/copilot", tags=["copilot"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class CopilotQueryRequest(BaseModel):
    question: str
    opportunity_id: Optional[uuid.UUID] = None
    account_id: Optional[uuid.UUID] = None
    top_k: int = 5


class Citation(BaseModel):
    snippet: str
    activity_id: Optional[str] = None
    date: Optional[str] = None


class CopilotQueryResponse(BaseModel):
    answer: str
    citations: list[Citation] = []
    clarification_needed: Optional[str] = None
    no_data: bool = False
    retrieved_chunks: int = 0


class CopilotDraftRequest(BaseModel):
    opportunity_id: uuid.UUID
    instruction: str  # 用户指令，例如"写一封跟进邮件，提醒对方 POC 结果"
    recipient_name: Optional[str] = None
    recipient_title: Optional[str] = None


class CopilotDraftResponse(BaseModel):
    pending_action_id: uuid.UUID
    subject: str
    body: str
    cta: str
    tone: str


class SendDraftRequest(BaseModel):
    to_email: str
    note: Optional[str] = None


# ── POST /copilot/query ───────────────────────────────────────────────────────

@router.post("/query", response_model=CopilotQueryResponse)
async def copilot_query(
    req: CopilotQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """RAG 检索 + LLM 问答，带 citation。"""
    try:
        safe_q = guard_input(req.question)
    except GuardViolation as e:
        await audit_guard_block(
            db, current_user,
            endpoint="copilot.query",
            violation=e,
            snippet=req.question,
            opportunity_id=req.opportunity_id,
        )
        raise HTTPException(400, detail=http_detail(e))

    # Build context
    context_parts = []
    opp = None
    if req.opportunity_id:
        opp = await db.get(Opportunity, req.opportunity_id)
        if opp:
            context_parts.append(
                f"当前商机：{opp.name}，阶段：{opp.stage}，"
                f"金额：{opp.amount}，健康度：{opp.health_status}"
            )

    # RAG retrieval
    chunks = await search_memory(
        db,
        query=safe_q,
        opportunity_id=req.opportunity_id,
        return_n=req.top_k,
    )

    if not chunks:
        # No data — still ask LLM to generate a helpful response
        rag_context = "（无相关历史纪要记录）"
    else:
        rag_context = "\n\n".join(
            f"[片段 {i+1}，score={float(c.get('score') or 0):.2f}]\n{c['content']}"
            for i, c in enumerate(chunks)
        )

    user_msg = (
        f"当前背景：{'; '.join(context_parts) or '无'}\n\n"
        f"检索到的纪要片段：\n{rag_context}\n\n"
        f"用户问题：{safe_q}"
    )

    result: dict = {}
    try:
        result = await call_llm_json(db, "synth", COPILOT_QUERY_SYSTEM, user_msg, max_tokens=1500)
        answer = guard_output(result.get("answer", ""))
    except GuardViolation as e:
        await audit_guard_block(
            db, current_user,
            endpoint="copilot.query.output",
            violation=e,
            snippet=str(result.get("answer", "")),
            opportunity_id=req.opportunity_id,
        )
        raise HTTPException(400, detail=http_detail(e))
    except Exception as e:
        raise HTTPException(500, f"LLM error: {e}")

    # Enrich citations with activity_id from chunks
    citations = []
    if result.get("citations"):
        for c in result.get("citations", []):
            citations.append(Citation(
                snippet=c.get("snippet", ""),
                activity_id=c.get("activity_id"),
                date=c.get("date"),
            ))
    elif chunks:
        for c in chunks[:3]:
            meta = c.get("metadata") or {}
            citations.append(Citation(
                snippet=(c.get("content") or "")[:180],
                activity_id=c.get("activity_id"),
                date=meta.get("meeting_date"),
            ))

    return CopilotQueryResponse(
        answer=answer,
        citations=citations,
        clarification_needed=result.get("clarification_needed"),
        no_data=result.get("no_data", False),
        retrieved_chunks=len(chunks),
    )


# ── POST /copilot/draft ───────────────────────────────────────────────────────

@router.post("/draft", response_model=CopilotDraftResponse)
async def copilot_draft(
    req: CopilotDraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成邮件草稿，存为 PendingAction L2，confirm 后才发送。"""
    try:
        safe_inst = guard_input(req.instruction)
    except GuardViolation as e:
        await audit_guard_block(
            db, current_user,
            endpoint="copilot.draft",
            violation=e,
            snippet=req.instruction,
            opportunity_id=req.opportunity_id,
        )
        raise HTTPException(400, detail=http_detail(e))

    opp = await db.get(Opportunity, req.opportunity_id)
    if not opp:
        raise HTTPException(404, "Opportunity not found")

    # RAG for context
    chunks = await search_memory(db, query=req.instruction, opportunity_id=req.opportunity_id, return_n=3)
    rag_ctx = "\n".join(c["content"][:200] for c in chunks) if chunks else ""

    user_msg = (
        f"商机：{opp.name}，阶段：{opp.stage}，竞对：{opp.competitor or '无'}\n"
        f"痛点：{opp.pain_points or '未记录'}\n"
        f"相关历史纪要：\n{rag_ctx or '（无）'}\n\n"
        f"收件人：{req.recipient_name or '对方联系人'} {req.recipient_title or ''}\n"
        f"写作指令：{safe_inst}"
    )

    try:
        result = await call_llm_json(db, "action_planner", COPILOT_DRAFT_SYSTEM, user_msg, max_tokens=800)
    except Exception as e:
        raise HTTPException(500, f"LLM error: {e}")

    # Output Guard
    try:
        result["body"] = guard_output(result.get("body", ""))
        result["subject"] = guard_output(result.get("subject", "") or "")
    except GuardViolation as e:
        await audit_guard_block(
            db, current_user,
            endpoint="copilot.draft.output",
            violation=e,
            snippet=result.get("body", ""),
            opportunity_id=req.opportunity_id,
        )
        raise HTTPException(400, detail=http_detail(e))

    # Create PendingAction L2
    pending = PendingAction(
        opportunity_id=req.opportunity_id,
        created_by=current_user.id,
        level="L2",
        action_type="email_draft",
        payload={
            "subject": result.get("subject", ""),
            "body": result.get("body", ""),
            "cta": result.get("cta", ""),
            "tone": result.get("tone", "formal"),
            "instruction": safe_inst,
            "recipient_name": req.recipient_name,
            "recipient_title": req.recipient_title,
        },
        status="pending",
    )
    db.add(pending)
    await db.commit()
    try:
        from app.services.dingtalk import enqueue_dingtalk
        enqueue_dingtalk("email_draft", {
            "opportunity_id": str(req.opportunity_id),
            "opp_name": opp.name,
            "subject": result.get("subject", ""),
            "pending_action_id": str(pending.id),
        })
    except Exception:
        pass

    return CopilotDraftResponse(
        pending_action_id=pending.id,
        subject=result.get("subject", ""),
        body=result.get("body", ""),
        cta=result.get("cta", ""),
        tone=result.get("tone", "formal"),
    )


# ── POST /copilot/draft/{id}/send ─────────────────────────────────────────────

@router.post("/draft/{pending_id}/send")
async def send_draft(
    pending_id: uuid.UUID,
    body: SendDraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """确认发送邮件（MVP: MailHog / log）。"""
    pa = await db.get(PendingAction, pending_id)
    if not pa:
        raise HTTPException(404, "PendingAction not found")
    if pa.action_type != "email_draft":
        raise HTTPException(400, "Not an email draft")
    if pa.status != "pending":
        raise HTTPException(400, f"Already {pa.status}")

    payload = pa.payload or {}
    subject = payload.get("subject", "（无主题）")
    email_body = payload.get("body", "")

    # MVP: send via SMTP (MailHog) or log
    sent = await _send_email_mvp(
        to=body.to_email,
        subject=subject,
        body=email_body,
    )

    # Create Activity audit record
    from app.models.crm import Activity, ActivityType
    audit = Activity(
        opportunity_id=pa.opportunity_id,
        owner_id=current_user.id,
        activity_type=ActivityType.EMAIL,
        subject=f"已发送邮件：{subject}",
        body=f"收件人：{body.to_email}\n\n{email_body}",
    )
    db.add(audit)

    pa.status = "approved"
    pa.reviewed_by = current_user.id
    pa.review_note = body.note
    await db.commit()

    return {"sent": sent, "to": body.to_email, "subject": subject}


async def _send_email_mvp(to: str, subject: str, body: str) -> bool:
    """
    MVP 邮件发送：尝试 SMTP (MailHog localhost:1025)，失败则 log。
    """
    import smtplib
    from email.mime.text import MIMEText
    from app.core.config import settings

    smtp_host = getattr(settings, "SMTP_HOST", "localhost")
    smtp_port = getattr(settings, "SMTP_PORT", 1025)

    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = "montocrm@local"
        msg["To"] = to
        with smtplib.SMTP(smtp_host, smtp_port, timeout=3) as s:
            s.sendmail("montocrm@local", [to], msg.as_string())
        return True
    except Exception:
        # Graceful degradation: log only
        print(f"[copilot/draft/send] SMTP unavailable — logged: TO={to} SUBJECT={subject}")
        return False
