"""Admin 钉钉通知配置。Webhook/Secret 不在列表接口明文回显。"""
from __future__ import annotations
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security.deps import RequireAdmin, CurrentUser
from app.db.session import get_db
from app.models.llm_settings import LLMSettings
from app.services.dingtalk import mask_webhook_url, send_event

router = APIRouter(prefix="/admin/notify", tags=["Admin Notify"])


class NotifySettingsOut(BaseModel):
    enabled: bool
    webhook_url_masked: str = ""
    secret_configured: bool = False
    quiet_start: str
    quiet_end: str
    tz: str


class NotifySettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    webhook_url: Optional[str] = None
    secret: Optional[str] = None
    quiet_start: Optional[str] = None
    quiet_end: Optional[str] = None


class NotifyTestRequest(BaseModel):
    event: str = Field(default="test")
    text: str = "Admin 发送的测试消息"


def _row_config(row: LLMSettings | None) -> dict:
    return dict((row.notify_config or {}) if row else {})


def _public(cfg: dict) -> NotifySettingsOut:
    url = (cfg.get("webhook_url") or settings.DINGTALK_WEBHOOK_URL or "").strip()
    secret = (cfg.get("secret") or settings.DINGTALK_SECRET or "").strip()
    enabled = cfg.get("enabled")
    if enabled is None:
        enabled = settings.DINGTALK_ENABLED
    return NotifySettingsOut(
        enabled=bool(enabled),
        webhook_url_masked=mask_webhook_url(url),
        secret_configured=bool(secret),
        quiet_start=cfg.get("quiet_start") or settings.DINGTALK_QUIET_START,
        quiet_end=cfg.get("quiet_end") or settings.DINGTALK_QUIET_END,
        tz=settings.DINGTALK_TZ,
    )


@router.get("/dingtalk", response_model=NotifySettingsOut)
async def get_dingtalk(
    _: Annotated[None, RequireAdmin],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (await db.execute(select(LLMSettings).limit(1))).scalar_one_or_none()
    return _public(_row_config(row))


@router.put("/dingtalk", response_model=NotifySettingsOut)
async def put_dingtalk(
    body: NotifySettingsUpdate,
    _: Annotated[None, RequireAdmin],
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (await db.execute(select(LLMSettings).limit(1))).scalar_one_or_none()
    cfg = _row_config(row)
    if body.enabled is not None:
        cfg["enabled"] = body.enabled
    if body.webhook_url:
        cfg["webhook_url"] = body.webhook_url.strip()
    if body.secret:
        cfg["secret"] = body.secret.strip()
    if body.quiet_start:
        cfg["quiet_start"] = body.quiet_start
    if body.quiet_end:
        cfg["quiet_end"] = body.quiet_end
    if row:
        row.notify_config = cfg
        row.updated_by = current_user.id
    else:
        raise HTTPException(
            400,
            detail="请先在 Admin LLM 设置中保存一次全局配置，再填写钉钉 Webhook",
        )
    await db.commit()
    return _public(cfg)


@router.post("/dingtalk/test")
async def test_dingtalk(
    body: NotifyTestRequest,
    _: Annotated[None, RequireAdmin],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    row = (await db.execute(select(LLMSettings).limit(1))).scalar_one_or_none()
    result = send_event(
        body.event or "test",
        {"text": body.text, "event": body.event or "test"},
        notify_config=_row_config(row),
        force=True,
    )
    safe = {k: v for k, v in result.items() if k != "body"}
    if isinstance(result.get("body"), dict):
        safe["errcode"] = result["body"].get("errcode")
        safe["errmsg"] = result["body"].get("errmsg")
    return safe
