"""Admin RAG：检索测试 + reindex 状态。"""
from __future__ import annotations
import time
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security.deps import RequireAdmin
from app.db.session import get_db
from app.services.rag.reindex_status import get_status, set_status
from app.services.rag.retriever import search_memory

router = APIRouter(prefix="/admin/rag", tags=["Admin RAG"])


class RetrievalTestRequest(BaseModel):
    query: str
    opportunity_id: Optional[uuid.UUID] = None
    top_k: int = 5


class RetrievalTestResponse(BaseModel):
    raw_query: str
    rewritten_query: str
    retrieved_chunks: int
    latency_ms: int
    chunks: list[dict]


class ReindexRequest(BaseModel):
    limit: Optional[int] = None
    enqueue: bool = True


@router.post("/test-retrieval", response_model=RetrievalTestResponse)
async def test_retrieval(
    body: RetrievalTestRequest,
    _: Annotated[None, RequireAdmin],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    t0 = time.perf_counter()
    chunks = await search_memory(
        db,
        query=body.query,
        opportunity_id=body.opportunity_id,
        return_n=body.top_k,
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)
    rewritten = chunks[0].get("rewritten_query", body.query) if chunks else body.query
    slim = [
        {
            "chunk_id": c.get("chunk_id"),
            "activity_id": c.get("activity_id"),
            "score": c.get("score"),
            "snippet": (c.get("content") or "")[:400],
            "metadata": c.get("metadata") or {},
        }
        for c in chunks
    ]
    return RetrievalTestResponse(
        raw_query=body.query,
        rewritten_query=rewritten or body.query,
        retrieved_chunks=len(chunks),
        latency_ms=latency_ms,
        chunks=slim,
    )


@router.get("/reindex-status")
async def reindex_status(_: Annotated[None, RequireAdmin]):
    st = get_status()
    st["embedding_provider"] = settings.EMBEDDING_PROVIDER
    st["embedding_model"] = settings.EMBEDDING_MODEL
    st["embedding_dimension"] = settings.EMBEDDING_DIMENSION
    st["rerank_provider"] = settings.RERANK_PROVIDER
    st["rerank_model"] = settings.RERANK_MODEL
    st["hf_sidecar_url"] = settings.HF_SIDECAR_URL
    from app.services.rag.sidecar import sidecar_health
    st["hf_sidecar"] = await sidecar_health()
    st["hint"] = (
        "local/hash 不加载 torch。真 BGE 请先启动 sidecar："
        " powershell -File scripts/run_hf_sidecar.ps1 ，"
        " 再设 EMBEDDING_PROVIDER=sidecar 与 RERANK_PROVIDER=sidecar，然后 reindex。"
        " 维度必须为 1024（bge-m3）。"
    )
    return st


@router.post("/reindex")
async def trigger_reindex(
    body: ReindexRequest,
    _: Annotated[None, RequireAdmin],
):
    if get_status().get("status") == "running":
        raise HTTPException(409, detail="reindex already running")
    set_status(status="queued", error=None)
    if body.enqueue:
        try:
            from app.tasks.rag_reindex import run_reindex
            run_reindex.delay(body.limit)
            return {"ok": True, "queued": True}
        except Exception:
            pass
    from app.services.rag.reindex import reindex_all
    result = await reindex_all(limit=body.limit)
    return {"ok": True, "queued": False, **result}
