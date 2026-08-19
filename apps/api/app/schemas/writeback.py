"""Pydantic schemas for Writeback / Extract API"""
from __future__ import annotations
import uuid
from typing import Any, Optional
from pydantic import BaseModel, Field


class ExtractRequest(BaseModel):
    opportunity_id: uuid.UUID
    canonical_text: str = Field(..., min_length=20, max_length=20000)
    activity_id: Optional[uuid.UUID] = None  # 关联已有 Activity；不传则新建
    page_context: dict[str, Any] = Field(default_factory=dict)


class ContactUpdateItem(BaseModel):
    full_name: str
    title: Optional[str] = None
    role_in_deal: Optional[str] = None
    influence_level: Optional[int] = None
    notes: Optional[str] = None
    is_new: bool = False
    contact_id: Optional[uuid.UUID] = None


class TaskItem(BaseModel):
    title: str
    owner: Optional[str] = None
    due_date: Optional[str] = None
    priority: str = "MEDIUM"
    type: str = "OTHER"


class RiskFlagItem(BaseModel):
    rule: str
    description: str
    severity: str = "MEDIUM"


class WritebackProposal(BaseModel):
    contact_updates: list[ContactUpdateItem] = []
    new_contacts: list[ContactUpdateItem] = []
    opportunity_updates: dict[str, Any] = {}
    tasks: list[TaskItem] = []
    risk_flags: list[RiskFlagItem] = []
    reasoning: str = ""
    evidence: list[dict[str, Any]] = []
    stage_hint: Optional[str] = None
    structured_summary: Optional[str] = None


class ExtractResponse(BaseModel):
    pending_action_id: uuid.UUID
    proposal: WritebackProposal
    agents_activated: list[str]
    plan_reasoning: str = ""
    errors: list[dict[str, Any]] = []


class ConfirmItem(BaseModel):
    field: str
    accepted: bool = True
    override_value: Any = None


class PendingActionConfirmRequest(BaseModel):
    items: list[ConfirmItem] = Field(default_factory=list,
        description="逐项确认；空列表 = 接受全部")
    note: Optional[str] = None


class PendingActionRejectRequest(BaseModel):
    note: Optional[str] = None


class PendingActionResponse(BaseModel):
    id: uuid.UUID
    status: str
    opportunity_id: uuid.UUID
    action_type: str
    payload: dict[str, Any]
    created_at: Any
    review_note: Optional[str] = None

    class Config:
        from_attributes = True
