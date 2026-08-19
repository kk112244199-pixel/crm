"""P7 混合 RAG：关键词命中、RRF、改写/Rerank 降级、MRR、P95。"""
from __future__ import annotations
import asyncio
import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.eval.retrieval import evaluate_retrieval, rank_hybrid
from app.services.rag.chunker import extract_source_metadata
from app.services.rag.rerank import lexical_rerank, rerank_docs
from app.services.rag.retriever import keyword_search_memory, rewrite_query, search_memory
from app.services.rag.textutil import rrf_fuse, tokenize

GOLDEN = Path(__file__).resolve().parent / "golden" / "extract_writeback.json"


def _golden():
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_keyword_hits_customer_and_sku():
    docs = [
        {"chunk_id": "noise", "content": "周报：内部培训与行政事项。"},
        {"chunk_id": "g01", "content": "与亿联智造演示。竞争对手：用友 U9 在内部也做了演示。"},
        {"chunk_id": "other", "content": "华峰精密预算缩减 30%。"},
    ]
    hits = keyword_search_memory("用友 U9 竞对", docs, top_k=5)
    assert hits
    assert hits[0]["chunk_id"] == "g01"
    hits2 = keyword_search_memory("亿联智造", docs, top_k=5)
    assert hits2[0]["chunk_id"] == "g01"


def test_rrf_merges_vector_and_keyword():
    vec = [
        {"chunk_id": "a", "content": "A", "score": 0.9},
        {"chunk_id": "b", "content": "B", "score": 0.8},
        {"chunk_id": "c", "content": "C", "score": 0.1},
    ]
    kw = [
        {"chunk_id": "c", "content": "C", "score": 0.99},
        {"chunk_id": "a", "content": "A", "score": 0.2},
    ]
    fused = rrf_fuse([vec, kw], k=60, weights=[1.0, 1.0])
    ids = [d["chunk_id"] for d in fused]
    assert ids[0] in ("a", "c")
    assert set(ids[:3]) == {"a", "b", "c"}
    assert "rrf_score" in fused[0]


def test_rrf_k_and_weights_configurable():
    left = [{"chunk_id": "only_vec", "content": "v"}]
    right = [{"chunk_id": "only_kw", "content": "k"}]
    even = rrf_fuse([left, right], k=60, weights=[1.0, 1.0])
    assert {d["chunk_id"] for d in even} == {"only_vec", "only_kw"}
    kw_heavy = rrf_fuse([left, right], k=10, weights=[0.1, 5.0])
    assert kw_heavy[0]["chunk_id"] == "only_kw"


@pytest.mark.asyncio
async def test_rerank_failure_falls_back_to_fused():
    docs = [
        {"chunk_id": "1", "content": "用友 U9 演示", "rrf_score": 0.02, "score": 0.02},
        {"chunk_id": "2", "content": "无关周报", "rrf_score": 0.01, "score": 0.01},
    ]
    with patch("app.services.rag.rerank.dashscope_rerank", new=AsyncMock(side_effect=RuntimeError("boom"))):
        with patch.object(settings, "RERANK_PROVIDER", "dashscope"):
            with patch.object(settings, "DASHSCOPE_API_KEY", "sk-test"):
                with patch.object(settings, "RERANK_ENABLED", True):
                    out = await rerank_docs("用友", docs, 2)
    assert len(out) == 2
    assert out[0]["chunk_id"] == "1"


@pytest.mark.asyncio
async def test_search_memory_rerank_exception_no_raise():
    fused = [{"chunk_id": "1", "content": "x", "score": 1.0, "opportunity_id": None, "activity_id": None}]

    async def boom(*_a, **_k):
        raise RuntimeError("rerank down")

    with (
        patch("app.services.rag.retriever.rewrite_query", new=AsyncMock(return_value="x")),
        patch("app.services.rag.retriever.expand_queries", new=AsyncMock(return_value=[])),
        patch("app.services.rag.retriever.embed_texts", new=AsyncMock(return_value=[[0.0] * 8])),
        patch("app.services.rag.retriever.vector_search", new=AsyncMock(return_value=fused)),
        patch("app.services.rag.retriever.keyword_search", new=AsyncMock(return_value=fused)),
        patch("app.services.rag.retriever.rerank_docs", new=boom),
    ):
        out = await search_memory(SimpleNamespace(), "用友", return_n=1)
    assert out and out[0]["chunk_id"] == "1"


@pytest.mark.asyncio
async def test_rewrite_timeout_falls_back_to_original():
    async def slow(*_a, **_k):
        await asyncio.sleep(2)
        return "should-not-win"

    with (
        patch("app.services.rag.retriever._llm_rewrite", new=slow),
        patch.object(settings, "RAG_REWRITE_TIMEOUT_SEC", 0.05),
    ):
        out = await rewrite_query("用友 U9 怎样？", SimpleNamespace())
    assert "用友" in out
    assert "should-not-win" not in out


def test_meeting_metadata_extracted():
    text = "【会议纪要】2026-08-01 与亿联智造\n参会人：王总、李明\n\n预算 380 万。"
    meta = extract_source_metadata(text)
    assert meta["meeting_date"] == "2026-08-01"
    assert "王总" in (meta["attendees"] or "")
    assert meta["source_title"] == "会议纪要"


def test_lexical_rerank_promotes_overlap():
    docs = [
        {"chunk_id": "weak", "content": "季度团建安排", "rrf_score": 0.05},
        {"chunk_id": "strong", "content": "华峰精密 西门子 低代码", "rrf_score": 0.04},
    ]
    out = lexical_rerank("华峰精密西门子", docs, 2)
    assert out[0]["chunk_id"] == "strong"


def test_mrr_hybrid_beats_p4_random_by_20pct():
    report = evaluate_retrieval(_golden())
    assert report["n_queries"] >= 8
    assert report["mrr_at_5_hybrid"] >= 0.8
    lift = report["relative_lift"]
    assert lift is not None and lift >= 0.20


def test_p95_in_memory_under_500ms():
    golden = _golden()
    docs = [
        {"chunk_id": it["id"], "content": it["canonical_text"]}
        for it in golden["items"]
        if it.get("canonical_text")
    ]
    queries = [it["question"] for it in golden["items"] if it.get("question")]
    rank_hybrid(queries[0], docs)
    lat = []
    for q in queries * 4:
        t0 = time.perf_counter()
        rank_hybrid(q, docs)
        lat.append((time.perf_counter() - t0) * 1000)
    lat.sort()
    p95 = lat[int(0.95 * (len(lat) - 1))]
    assert p95 <= 500, f"p95={p95:.1f}ms"


def test_tokenize_keeps_product_tokens():
    toks = tokenize("用友 U9 和 SAP")
    assert "u9" in toks
    assert "sap" in toks


@pytest.mark.asyncio
async def test_sidecar_embed_falls_back_to_hash():
    from app.services.rag.embedder import embed_texts, hash_embed
    with (
        patch.object(settings, "EMBEDDING_PROVIDER", "sidecar"),
        patch.object(settings, "EMBEDDING_DIMENSION", 8),
        patch("app.services.rag.sidecar.sidecar_embed", new=AsyncMock(return_value=None)),
    ):
        out = await embed_texts(["用友 U9"])
    assert len(out) == 1
    assert len(out[0]) == 8
    assert out[0] == hash_embed("用友 U9", 8)


@pytest.mark.asyncio
async def test_sidecar_rerank_falls_back_to_lexical():
    docs = [
        {"chunk_id": "1", "content": "用友 U9 演示", "rrf_score": 0.01},
        {"chunk_id": "2", "content": "无关周报", "rrf_score": 0.02},
    ]
    with (
        patch.object(settings, "RERANK_PROVIDER", "sidecar"),
        patch.object(settings, "RERANK_ENABLED", True),
        patch("app.services.rag.sidecar.sidecar_rerank", new=AsyncMock(return_value=None)),
    ):
        out = await rerank_docs("用友", docs, 2)
    assert out[0]["chunk_id"] == "1"

