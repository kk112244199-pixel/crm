from __future__ import annotations
import logging
from app.worker import celery_app

log = logging.getLogger("montocrm.reindex.task")


@celery_app.task(name="app.tasks.rag_reindex.run_reindex", queue="default")
def run_reindex(limit: int | None = None) -> dict:
    import asyncio
    from app.services.rag.reindex import reindex_all
    from app.services.rag.reindex_status import set_status
    try:
        return asyncio.run(reindex_all(limit=limit))
    except Exception as e:
        log.exception("reindex_failed")
        set_status(status="idle", error=str(e))
        return {"ok": False, "error": str(e)}
