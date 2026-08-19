"""Golden 语料上的检索 MRR。pytest/CI 用 hash；本机 sidecar 健康则用 BGE-M3。"""
from __future__ import annotations
import random
import time
from typing import Any, Callable

from app.services.rag.embedder import hash_embed
from app.services.rag.rerank import lexical_rerank
from app.services.rag.retriever import keyword_search_memory
from app.services.rag.textutil import rrf_fuse

EmbedFn = Callable[[str], list[float]]


def _cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n <= 0:
        return 0.0
    return float(sum(a[i] * b[i] for i in range(n)))


def _mrr(ranked_ids: list[str], relevant: str, k: int = 5) -> float:
    for i, cid in enumerate(ranked_ids[:k], start=1):
        if cid == relevant:
            return 1.0 / i
    return 0.0


def resolve_eval_embedder() -> tuple[EmbedFn, str]:
    """pytest/CI 用 hash；本机 sidecar 健康则用 BGE。"""
    import os

    dim = 256
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("CI"):
        return (lambda t: hash_embed(t, dim)), "hash"
    try:
        import httpx
        from app.core.config import settings
        from app.eval.dashscope_ragas import SidecarEmbeddings

        base = (settings.HF_SIDECAR_URL or "http://127.0.0.1:18090").rstrip("/")
        health = httpx.get(f"{base}/health", timeout=3.0)
        if health.status_code == 200:
            model = SidecarEmbeddings(
                base_url=base,
                timeout_sec=float(settings.HF_SIDECAR_TIMEOUT_SEC or 120),
            )
            return model.embed_query, "bge_sidecar"
    except Exception:
        pass
    return (lambda t: hash_embed(t, dim)), "hash"


def build_corpus(golden: dict[str, Any]) -> list[dict]:
    docs = []
    for item in golden.get("items") or []:
        text = item.get("canonical_text") or ""
        if not text:
            continue
        docs.append({"chunk_id": item["id"], "content": text, "metadata": {"meeting_date": item.get("meeting_date")}})
    return docs


def rank_hybrid(
    query: str,
    docs: list[dict],
    *,
    embed_fn: EmbedFn | None = None,
    doc_vecs: dict[str, list[float]] | None = None,
    return_n: int = 5,
) -> list[dict]:
    fn = embed_fn or (lambda t: hash_embed(t, 256))
    q_emb = fn(query)
    vec_ranked = []
    for d in docs:
        dvec = (doc_vecs or {}).get(d["chunk_id"]) or fn(d["content"])
        row = dict(d)
        row["score"] = _cosine(q_emb, dvec)
        vec_ranked.append(row)
    vec_ranked.sort(key=lambda x: -float(x["score"]))
    kw = keyword_search_memory(query, docs, top_k=20)
    fused = rrf_fuse([vec_ranked[:20], kw], k=60, weights=[1.0, 1.0])
    return lexical_rerank(query, fused[:20], return_n)


def rank_random(docs: list[dict], rng: random.Random) -> list[dict]:
    items = [dict(d) for d in docs]
    rng.shuffle(items)
    return items


def evaluate_retrieval(golden: dict[str, Any]) -> dict[str, Any]:
    docs = build_corpus(golden)
    items = [it for it in golden.get("items") or [] if it.get("canonical_text") and it.get("question")]
    embed_fn, backend = resolve_eval_embedder()
    doc_vecs = {d["chunk_id"]: embed_fn(d["content"]) for d in docs}
    rng = random.Random(42)
    hybrid_scores: list[float] = []
    p4_scores: list[float] = []
    t0 = time.perf_counter()
    lat_ms: list[float] = []
    for it in items:
        q = it["question"]
        t1 = time.perf_counter()
        ranked = rank_hybrid(q, docs, embed_fn=embed_fn, doc_vecs=doc_vecs)
        lat_ms.append((time.perf_counter() - t1) * 1000)
        hybrid_scores.append(_mrr([d["chunk_id"] for d in ranked], it["id"], k=5))
        p4_scores.append(_mrr([d["chunk_id"] for d in rank_random(docs, rng)], it["id"], k=5))
    elapsed = time.perf_counter() - t0
    mrr_h = sum(hybrid_scores) / max(len(hybrid_scores), 1)
    mrr_p4 = sum(p4_scores) / max(len(p4_scores), 1)
    lift = (mrr_h - mrr_p4) / mrr_p4 if mrr_p4 > 1e-9 else None
    p95 = sorted(lat_ms)[int(0.95 * (len(lat_ms) - 1))] if lat_ms else 0.0
    if backend == "bge_sidecar":
        note = "向量=线上同一 sidecar BGE-M3；关键词 RRF + lexical rerank。P4 基线仍为随机排列。"
    else:
        note = (
            "向量=hash（CI / sidecar 不可达）。P4 基线为随机排列。"
            "本机请设 EMBEDDING_PROVIDER=sidecar 并启动 18090。"
        )
    return {
        "n_queries": len(items),
        "n_docs": len(docs),
        "embedding_backend": backend,
        "mrr_at_5_hybrid": round(mrr_h, 4),
        "mrr_at_5_p4_random_vector": round(mrr_p4, 4),
        "relative_lift": None if lift is None else round(lift, 4),
        "p95_ms_in_memory": round(p95, 2),
        "total_seconds": round(elapsed, 3),
        "note": note,
    }
