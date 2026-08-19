"""
Audit service — 统一写入 AuditLog
用法：await write_audit(db, actor=user, action="pending_action.confirm", ...)
"""
from __future__ import annotations
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog
from app.models.user import User


async def write_audit(
    db: AsyncSession,
    *,
    actor: User,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | None = None,
    opportunity_id: uuid.UUID | None = None,
    detail: dict | None = None,
) -> AuditLog:
    log = AuditLog(
        actor_id=actor.id,
        actor_role=actor.role.value if hasattr(actor.role, "value") else str(actor.role),
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        opportunity_id=opportunity_id,
        detail=detail or {},
    )
    db.add(log)
    # Don't commit here — caller commits the full transaction
    return log
