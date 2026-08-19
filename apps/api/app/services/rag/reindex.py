"""全量重建 memory_chunks embedding（从 Activity.canonical_text 再 ingest）。"""
from __future__ import annotations
import asyncio
import logging
import time

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.crm import Activity
from app.services.rag.ingest import ingest_activity
from app.services.rag.reindex_status import set_status

log = logging.getLogger("montocrm.reindex")


async def reindex_all(*, limit: int | None = None) -> dict:
    set_status(status="running", error=None, last_run=None)
    t0 = time.perf_counter()
    n_act = 0
    n_chunks = 0
    async with AsyncSessionLocal() as db:
        q = select(Activity).where(Activity.canonical_text.isnot(None))
        if limit:
            q = q.limit(limit)
        rows = (await db.execute(q)).scalars().all()
        for act in rows:
            text = (act.canonical_text or "").strip()
            if not text or not act.opportunity_id:
                continue
            n_act += 1
            n_chunks += await ingest_activity(
                db,
                opportunity_id=act.opportunity_id,
                activity_id=act.id,
                canonical_text=text,
                metadata={"reindex": True},
            )
            set_status(status="running", chunks=n_chunks)
    elapsed = time.perf_counter() - t0
    set_status(
        status="idle",
        needs_reindex=False,
        reason=None,
        last_run={"activities": n_act, "chunks": n_chunks, "seconds": round(elapsed, 2)},
        chunks=n_chunks,
        error=None,
    )
    log.info("reindex_done activities=%s chunks=%s seconds=%.2f", n_act, n_chunks, elapsed)
    return {"activities": n_act, "chunks": n_chunks, "seconds": round(elapsed, 2)}


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    import argparse
    p = argparse.ArgumentParser(description="Rebuild RAG embeddings from activities")
    p.add_argument("--full", action="store_true", help="re-ingest all activities with canonical_text")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()
    if not args.full and args.limit is None:
        args.full = True
    result = asyncio.run(reindex_all(limit=args.limit))
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
