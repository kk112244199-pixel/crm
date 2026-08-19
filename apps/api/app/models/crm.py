import enum
import uuid
from sqlalchemy import String, Text, Enum as SAEnum, Numeric, Date, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


# ── Enums ────────────────────────────────────────────────────────────────────

class OppStage(str, enum.Enum):
    PROSPECTING = "PROSPECTING"
    QUALIFICATION = "QUALIFICATION"
    NEEDS_ANALYSIS = "NEEDS_ANALYSIS"
    VALUE_PROPOSITION = "VALUE_PROPOSITION"
    PROPOSAL = "PROPOSAL"
    NEGOTIATION = "NEGOTIATION"
    CLOSED_WON = "CLOSED_WON"
    CLOSED_LOST = "CLOSED_LOST"


class HealthStatus(str, enum.Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class RoleInDeal(str, enum.Enum):
    ECONOMIC_BUYER = "ECONOMIC_BUYER"
    TECHNICAL_BUYER = "TECHNICAL_BUYER"
    CHAMPION = "CHAMPION"
    BLOCKER = "BLOCKER"
    INFLUENCER = "INFLUENCER"
    UNKNOWN = "UNKNOWN"


class ActivityType(str, enum.Enum):
    MEETING = "MEETING"
    CALL = "CALL"
    EMAIL = "EMAIL"
    NOTE = "NOTE"
    TASK = "TASK"


# ── Account ──────────────────────────────────────────────────────────────────

class Account(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "accounts"

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    industry: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    employee_count: Mapped[int | None] = mapped_column(Integer)
    website: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    contacts: Mapped[list["Contact"]] = relationship(back_populates="account")
    opportunities: Mapped[list["Opportunity"]] = relationship(back_populates="account")


# ── Contact ──────────────────────────────────────────────────────────────────

class Contact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "contacts"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    role_in_deal: Mapped[RoleInDeal] = mapped_column(
        SAEnum(RoleInDeal, name="role_in_deal"), default=RoleInDeal.UNKNOWN
    )
    influence_level: Mapped[int | None] = mapped_column(Integer)  # 1-5
    notes: Mapped[str | None] = mapped_column(Text)

    account: Mapped["Account"] = relationship(back_populates="contacts")


# ── Opportunity ───────────────────────────────────────────────────────────────

class Opportunity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "opportunities"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    stage: Mapped[OppStage] = mapped_column(
        SAEnum(OppStage, name="opp_stage"), default=OppStage.PROSPECTING
    )
    amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    expected_close_date: Mapped[str | None] = mapped_column(Date)
    pain_points: Mapped[str | None] = mapped_column(Text)
    competitor: Mapped[str | None] = mapped_column(String(500))
    budget_status: Mapped[str | None] = mapped_column(String(100))
    meddic_gaps: Mapped[dict | None] = mapped_column(JSONB)
    health_score: Mapped[int | None] = mapped_column(Integer)  # 0-100
    health_status: Mapped[HealthStatus | None] = mapped_column(
        SAEnum(HealthStatus, name="health_status")
    )
    health_deductions: Mapped[dict | None] = mapped_column(JSONB)  # {rule: score}

    account: Mapped["Account"] = relationship(back_populates="opportunities")
    activities: Mapped[list["Activity"]] = relationship(back_populates="opportunity")


# ── Activity ─────────────────────────────────────────────────────────────────

class Activity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "activities"

    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    activity_type: Mapped[ActivityType] = mapped_column(
        SAEnum(ActivityType, name="activity_type"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    canonical_text: Mapped[str | None] = mapped_column(Text)  # 预处理后纪要原文
    structured_summary: Mapped[dict | None] = mapped_column(JSONB)  # Synth 输出

    opportunity: Mapped["Opportunity"] = relationship(back_populates="activities")
