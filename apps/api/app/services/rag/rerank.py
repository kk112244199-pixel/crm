"""Rerank：Dashscope Cross-Encoder 或本地 lexical；失败降级为输入顺序。"""
from __future__ import annotations
import logging

from app.core.config import settings
from app.services.rag.textutil import tokenize

log = logging.getLogger("montocrm.rerank")


def _overlap(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a)


def lexical_rerank(query: str, docs: list[dict], return_n: int) -> list[dict]:
    qtok = tokenize(query)
    scored: list[tuple[float, dict]] = []
    for d in docs:
        ov = _overlap(qtok, tokenize(d.get("content") or ""))
        fused = ov * 0.7 + float(d.get("rrf_score") or d.get("score") or 0) * 0.3
        scored.append((fused, d))
    scored.sort(key=lambda x: -x[0])
    out = []
    for sc, d in scored[: max(return_n, 0)]:
        row = dict(d)
        row["rerank_score"] = round(sc, 4)
        row["score"] = row["rerank_score"]
        out.append(row)
    return out


async def dashscope_rerank(query: str, docs: list[dict], return_n: int) -> list[dict] | None:
    if not settings.DASHSCOPE_API_KEY or not docs:
        return None
    try:
        import httpx
        url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
        payload = {
            "model": settings.RERANK_MODEL if "gte" in (settings.RERANK_MODEL or "").lower() else "gte-rerank",
            "input": {
                "query": query,
                "documents": [d.get("content", "")[:4000] for d in docs],
            },
            "parameters": {"top_n": return_n, "return_documents": False},
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        results = (data.get("output") or {}).get("results") or []
        if not results:
            return None
        reranked = []
        for item in results[:return_n]:
            idx = int(item.get("index", 0))
            if 0 <= idx < len(docs):
                row = dict(docs[idx])
                row["rerank_score"] = float(item.get("relevance_score") or 0)
                row["score"] = row["rerank_score"]
                reranked.append(row)
        return reranked or None
    except Exception as e:
        log.warning("dashscope_rerank_failed: %s", e)
        return None


async def rerank_docs(query: str, docs: list[dict], return_n: int) -> list[dict]:
    if not docs:
        return []
    n = max(return_n, 0)
    if not settings.RERANK_ENABLED:
        return docs[:n]
    provider = (settings.RERANK_PROVIDER or "local").lower()
    try:
        if provider in ("sidecar", "hf", "huggingface"):
            from app.services.rag.sidecar import sidecar_rerank
            remote = await sidecar_rerank(query, docs, n)
            if remote is not None:
                return remote
        if provider in ("dashscope", "gte"):
            remote = await dashscope_rerank(query, docs, n)
            if remote is not None:
                return remote
        return lexical_rerank(query, docs, n)
    except Exception as e:
        log.warning("rerank_failed: %s", e)
        return docs[:n]
