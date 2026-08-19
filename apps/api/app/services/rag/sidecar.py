"""调用本机 HF sidecar；失败返回 None，由调用方降级。"""
from __future__ import annotations
import logging
from typing import Any

from app.core.config import settings

log = logging.getLogger("montocrm.hf_sidecar")


def sidecar_base() -> str:
    return (settings.HF_SIDECAR_URL or "").rstrip("/")


async def sidecar_embed(texts: list[str]) -> list[list[float]] | None:
    base = sidecar_base()
    if not base or not texts:
        return None
    try:
        import httpx
        timeout = float(settings.HF_SIDECAR_TIMEOUT_SEC or 60)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{base}/embed", json={"texts": texts})
            resp.raise_for_status()
            data = resp.json()
        embs = data.get("embeddings") or []
        if len(embs) != len(texts):
            log.warning("sidecar_embed_count_mismatch")
            return None
        dim = settings.EMBEDDING_DIMENSION
        out: list[list[float]] = []
        for v in embs:
            vec = [float(x) for x in v]
            if len(vec) != dim:
                log.warning("sidecar_embed_dim_mismatch got=%s want=%s", len(vec), dim)
                return None
            out.append(vec)
        return out
    except Exception as e:
        log.warning("sidecar_embed_failed: %s", e)
        return None


async def sidecar_rerank(query: str, docs: list[dict], return_n: int) -> list[dict] | None:
    base = sidecar_base()
    if not base or not docs:
        return None
    try:
        import httpx
        timeout = float(settings.HF_SIDECAR_TIMEOUT_SEC or 60)
        payload = {
            "query": query,
            "documents": [d.get("content", "")[:4000] for d in docs],
            "top_n": return_n,
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{base}/rerank", json=payload)
            resp.raise_for_status()
            data = resp.json()
        results = data.get("results") or []
        if not results:
            return None
        reranked: list[dict] = []
        for item in results[:return_n]:
            idx = int(item.get("index", 0))
            if 0 <= idx < len(docs):
                row = dict(docs[idx])
                row["rerank_score"] = float(item.get("score") or 0)
                row["score"] = row["rerank_score"]
                reranked.append(row)
        return reranked or None
    except Exception as e:
        log.warning("sidecar_rerank_failed: %s", e)
        return None


async def sidecar_health() -> dict[str, Any] | None:
    base = sidecar_base()
    if not base:
        return None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{base}/health")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None
