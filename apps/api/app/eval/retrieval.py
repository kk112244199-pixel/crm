"""Golden 语料上的检索 MRR（内存混合检索，不依赖 DB / 远程 Embedding）。"""
from __future__ import annotations
import random
import time
from typing import Any

from app.services.rag.embedder import hash_embed
from app.services.rag.rerank import lexical_rerank
from app.services.rag.retriever import keyword_search_memory
from app.services.rag.textutil import rrf_fuse


def _cosine(a: list[float], b: list[float]) -> float:
    return float(sum(x * y for x, y in zip(a, b)))


def _mrr(ranked_ids: list[str], relevant: str, k: int = 5) -> float:
    for i, cid in enumerate(ranked_ids[:k], start=1):
        if cid == relevant:
            return 1.0 / i
    return 0.0


def build_corpus(golden: dict[str, Any]) -> list[dict]:
    docs = []
    for item in golden.get("items") or []:
        text = item.get("canonical_text") or ""
        if not text:
            continue
        docs.append({"chunk_id": item["id"], "content": text, "metadata": {"meeting_date": item.get("meeting_date")}})
    return docs


def rank_hybrid(query: str, docs: list[dict], dim: int = 256, return_n: int = 5) -> list[dict]:
    q_emb = hash_embed(query, dim)
    vec_ranked = []
    for d in docs:
        sc = _cosine(q_emb, hash_embed(d["content"], dim))
        row = dict(d)
        row["score"] = sc
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
    rng = random.Random(42)
    hybrid_scores: list[float] = []
    p4_scores: list[float] = []
    t0 = time.perf_counter()
    n_lat = 0
    lat_ms: list[float] = []
    for it in items:
        q = it["question"]
        t1 = time.perf_counter()
        ranked = rank_hybrid(q, docs)
        lat_ms.append((time.perf_counter() - t1) * 1000)
        n_lat += 1
        hybrid_scores.append(_mrr([d["chunk_id"] for d in ranked], it["id"], k=5))
        p4_scores.append(_mrr([d["chunk_id"] for d in rank_random(docs, rng)], it["id"], k=5))
    elapsed = time.perf_counter() - t0
    mrr_h = sum(hybrid_scores) / max(len(hybrid_scores), 1)
    mrr_p4 = sum(p4_scores) / max(len(p4_scores), 1)
    lift = (mrr_h - mrr_p4) / mrr_p4 if mrr_p4 > 1e-9 else None
    p95 = sorted(lat_ms)[int(0.95 * (len(lat_ms) - 1))] if lat_ms else 0.0
    return {
        "n_queries": len(items),
        "n_docs": len(docs),
        "mrr_at_5_hybrid": round(mrr_h, 4),
        "mrr_at_5_p4_random_vector": round(mrr_p4, 4),
        "relative_lift": None if lift is None else round(lift, 4),
        "p95_ms_in_memory": round(p95, 2),
        "total_seconds": round(elapsed, 3),
        "note": (
            "P4 基线为随机向量召回（当时 local embed=高斯噪声），"
            "MRR@5 期望约 0.2–0.3。P7 关键词 + hash 向量 RRF + lexical rerank。"
        ),
    }
