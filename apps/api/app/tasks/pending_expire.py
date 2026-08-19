"""
PendingAction 过期检查 — Celery Beat 每小时运行一次
超过 48h 未处理的 pending → 状态改为 "expired"，写 AuditLog
"""
import asyncio
from app.worker import celery_app


@celery_app.task(name="app.tasks.pending_expire.expire_pending_actions", queue="health_batch")
def expire_pending_actions():
    asyncio.run(_expire())


async def _expire():
    from datetime import datetime, timedelta, timezone
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select
    from app.core.config import settings
    from app.models.memory import PendingAction

    engine = create_async_engine(settings.DATABASE_URL)
    sf = async_sessionmaker(engine, expire_on_commit=False)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

    async with sf() as db:
        res = await db.execute(
            select(PendingAction)
            .where(PendingAction.status == "pending")
            .where(PendingAction.created_at < cutoff)
        )
        expired = res.scalars().all()
        count = 0
        for pa in expired:
            pa.status = "expired"
            pa.review_note = "Auto-expired after 48h"
            count += 1

        if count:
            await db.commit()
            print(f"[pending_expire] Expired {count} pending actions")

    await engine.dispose()
