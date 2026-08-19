"""
健康度批算任务（P3 实现）
触发路径：
  1. Celery Beat Cron 每日 02:00
  2. Activity 写回确认后由 API 触发 .delay()
"""
import asyncio
from app.worker import celery_app


@celery_app.task(name="app.tasks.health_batch.run_full_health_batch", queue="health_batch")
def run_full_health_batch():
    """遍历所有活跃商机，运行 H001–H008 规则引擎。"""
    asyncio.run(_run_batch())


async def _run_batch():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select
    from app.core.config import settings
    from app.models.crm import Opportunity, OppStage
    from app.services.health.calculator import recalculate_opp_health

    engine = create_async_engine(settings.DATABASE_URL)
    sf = async_sessionmaker(engine, expire_on_commit=False)

    async with sf() as db:
        res = await db.execute(
            select(Opportunity.id).where(
                Opportunity.stage.notin_([OppStage.CLOSED_WON, OppStage.CLOSED_LOST])
            )
        )
        ids = [r[0] for r in res.fetchall()]

    # Process in sub-sessions to avoid long-lived connections
    async with sf() as db:
        for opp_id in ids:
            try:
                await recalculate_opp_health(db, opp_id)
            except Exception as e:
                # Log and continue
                print(f"[health_batch] Error on {opp_id}: {e}")

    await engine.dispose()


@celery_app.task(name="app.tasks.health_batch.run_single_health", queue="health_batch")
def run_single_health(opportunity_id: str):
    """写回后触发单条商机健康度重算。"""
    asyncio.run(_run_single(opportunity_id))


async def _run_single(opportunity_id: str):
    import uuid
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.core.config import settings
    from app.services.health.calculator import recalculate_opp_health

    engine = create_async_engine(settings.DATABASE_URL)
    sf = async_sessionmaker(engine, expire_on_commit=False)

    async with sf() as db:
        await recalculate_opp_health(db, uuid.UUID(opportunity_id))

    await engine.dispose()
