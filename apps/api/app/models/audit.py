"""
AuditLog — L1+ 操作审计记录
每条 confirm / reject / stage_change / amount_change 都写一条
"""
import uuid
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class AuditLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    # Who
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)

    # What
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # e.g. "pending_action.confirm", "opportunity.stage_change", "opportunity.amount_change"

    # Context
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)

    # Payload: before/after values
    detail: Mapped[dict | None] = mapped_column(JSONB)

    # Optional: related opportunity
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id"), index=True
    )
