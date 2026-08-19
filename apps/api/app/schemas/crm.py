import uuid
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.crm import OppStage, HealthStatus, RoleInDeal, ActivityType


# ── Account ──────────────────────────────────────────────────────────────────

class AccountCreate(BaseModel):
    name: str
    industry: Optional[str] = None
    region: Optional[str] = None
    employee_count: Optional[int] = None
    website: Optional[str] = None
    description: Optional[str] = None


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    region: Optional[str] = None
    employee_count: Optional[int] = None
    website: Optional[str] = None
    description: Optional[str] = None


class AccountOut(AccountCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ── Contact ──────────────────────────────────────────────────────────────────

class ContactCreate(BaseModel):
    account_id: uuid.UUID
    full_name: str
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role_in_deal: RoleInDeal = RoleInDeal.UNKNOWN
    influence_level: Optional[int] = None
    notes: Optional[str] = None


class ContactUpdate(BaseModel):
    full_name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role_in_deal: Optional[RoleInDeal] = None
    influence_level: Optional[int] = None
    notes: Optional[str] = None


class ContactOut(ContactCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ── Opportunity ───────────────────────────────────────────────────────────────

class OpportunityCreate(BaseModel):
    account_id: uuid.UUID
    name: str
    stage: OppStage = OppStage.PROSPECTING
    amount: Optional[float] = None
    expected_close_date: Optional[date] = None
    pain_points: Optional[str] = None
    competitor: Optional[str] = None
    budget_status: Optional[str] = None


class OpportunityUpdate(BaseModel):
    name: Optional[str] = None
    stage: Optional[OppStage] = None
    amount: Optional[float] = None
    expected_close_date: Optional[date] = None
    pain_points: Optional[str] = None
    competitor: Optional[str] = None
    budget_status: Optional[str] = None


class OpportunityOut(OpportunityCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    health_score: Optional[int] = None
    health_status: Optional[HealthStatus] = None
    created_at: datetime
    updated_at: datetime


# ── Activity ─────────────────────────────────────────────────────────────────

class ActivityCreate(BaseModel):
    opportunity_id: uuid.UUID
    activity_type: ActivityType
    subject: str
    body: Optional[str] = None
    canonical_text: Optional[str] = None


class ActivityUpdate(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    canonical_text: Optional[str] = None


class ActivityOut(ActivityCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    owner_id: uuid.UUID
    structured_summary: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
