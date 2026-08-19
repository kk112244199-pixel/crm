"""
Audit Log API — Manager / Admin 专用
GET /audit/logs   → 操作日志列表（按 opportunity / action / actor 过滤）
"""
from __future__ import annotations
import uuid
from typing import Optional, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.core.security.deps import get_current_user
from app.models.user import User, UserRole
from app.models.audit import AuditLog

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditLogOut(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID
    actor_role: str
    action: str
    resource_type: str
    resource_id: Optional[uuid.UUID]
    opportunity_id: Optional[uuid.UUID]
    detail: Optional[dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/logs", response_model=list[AuditLogOut])
async def list_audit_logs(
    opportunity_id: Optional[uuid.UUID] = None,
    action: Optional[str] = None,
    actor_id: Optional[uuid.UUID] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manager+ 查看审计日志。"""
    if current_user.role == UserRole.AE:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    q = select(AuditLog).order_by(AuditLog.created_at.desc())
    if opportunity_id:
        q = q.where(AuditLog.opportunity_id == opportunity_id)
    if action:
        q = q.where(AuditLog.action == action)
    if actor_id:
        q = q.where(AuditLog.actor_id == actor_id)
    q = q.limit(min(limit, 200))
    result = await db.execute(q)
    return result.scalars().all()
