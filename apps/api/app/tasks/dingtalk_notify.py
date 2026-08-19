"""Celery：钉钉发送，最多 3 次指数退避；失败写 audit。"""
from __future__ import annotations
import logging

from app.worker import celery_app

log = logging.getLogger("montocrm.dingtalk.task")


@celery_app.task(
    bind=True,
    name="app.tasks.dingtalk_notify.send_dingtalk_event",
    max_retries=3,
    autoretry_for=(),
)
def send_dingtalk_event(self, event: str, context: dict) -> dict:
    from app.services.dingtalk import send_event

    try:
        result = send_event(event, context or {})
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
    if result.get("deferred") or result.get("skipped"):
        return result
    if result.get("ok"):
        return result
    err = result.get("error") or "send_failed"
    if self.request.retries < self.max_retries:
        countdown = 2 ** self.request.retries
        raise self.retry(countdown=countdown, exc=RuntimeError(err))
    _audit_fail(event, err, context)
    return {"ok": False, "error": err, "retries_exhausted": True}


@celery_app.task(name="app.tasks.dingtalk_notify.flush_delayed")
def flush_delayed() -> dict:
    from app.services.dingtalk import in_quiet_hours, pop_delayed, send_event

    if in_quiet_hours():
        return {"ok": True, "skipped": "quiet"}
    items = pop_delayed(100)
    sent = 0
    for item in items:
        r = send_event(item.get("event") or "test", item.get("context") or {})
        if r.get("ok") and not r.get("deferred"):
            sent += 1
    return {"ok": True, "flushed": len(items), "sent": sent}


def _audit_fail(event: str, error: str, context: dict) -> None:
    import asyncio

    async def _run():
        from sqlalchemy import select
        from app.db.session import AsyncSessionLocal
        from app.models.user import User, UserRole
        from app.services.audit import write_audit

        async with AsyncSessionLocal() as db:
            admin = (
                await db.execute(select(User).where(User.role == UserRole.ADMIN).limit(1))
            ).scalar_one_or_none()
            if not admin:
                log.error("dingtalk_fail_no_admin event=%s error=%s", event, error)
                return
            await write_audit(
                db,
                actor=admin,
                action="dingtalk.send_failed",
                resource_type="notify",
                opportunity_id=None,
                detail={"event": event, "error": error, "context_keys": list((context or {}).keys())},
            )
            await db.commit()

    try:
        asyncio.run(_run())
    except Exception:
        log.exception("dingtalk_audit_fail")
