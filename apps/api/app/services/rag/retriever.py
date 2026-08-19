"""
混合检索：Query 改写 → 向量 + 关键词 → RRF → Rerank。
改写超时 / Rerank 失败均降级，不抛 500。
"""
from __future__ import annotations
import asyncio
import logging
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.config import settings
from app.services.rag.embedder import embed_texts
from app.services.rag.rerank import rerank_docs
from app.services.rag.textutil import rrf_fuse, tokenize

log = logging.getLogger("montocrm.retriever")

_REWRITE_SYS = (
    "你是检索改写器。把销售口语问题改写成便于在会议纪要中检索的短句，"
    "必须保留客户名、产品型号、金额、人名等关键词。只输出改写后的一句中文，不要引号和解释。"
)


def _cleanup_query(query: str) -> str:
    q = re.sub(r"[？?！!。，,]", " ", query or "").strip()
    return re.sub(r"\s+", " ", q)


def _escape_like(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _query_tokens(query: str) -> list[str]:
    found = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9.]{2,}", query or "")
    out: list[str] = []
    seen: set[str] = set()
    for t in found:
        tl = t.lower()
        if tl not in seen:
            seen.add(tl)
            out.append(t)
    return out[:8]


def _row_to_hit(r) -> dict:
    meta = r.metadata if hasattr(r, "metadata") else None
    if meta is None:
        meta = {}
    return {
        "chunk_id": str(r.id),
        "opportunity_id": str(r.opportunity_id) if r.opportunity_id else None,
        "activity_id": str(r.activity_id) if r.activity_id else None,
        "content": r.content,
        "score": float(r.score) if r.score is not None else 0.0,
        "metadata": meta if isinstance(meta, dict) else {},
    }


async def _llm_rewrite(query: str, db: AsyncSession) -> str:
    cleaned = _cleanup_query(query)
    has_key = bool(
        settings.DASHSCOPE_API_KEY or settings.DEEPSEEK_API_KEY or settings.OPENAI_API_KEY
    )
    if not has_key:
        return cleaned or (query or "").strip()
    from app.core.llm.resolver import resolve_llm

    client, model = await resolve_llm(db, agent="planner")
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _REWRITE_SYS},
            {"role": "user", "content": query},
        ],
        temperature=0.1,
        max_tokens=80,
    )
    raw = (resp.choices[0].message.content or "").strip()
    raw = raw.strip("\"'`")
    if raw.startswith("{"):
        return cleaned or query.strip()
    return raw[:200] if raw else (cleaned or query.strip())


async def rewrite_query(query: str, db: AsyncSession) -> str:
    """必做改写节点：超时或失败降级为清洗后的原 query。"""
    cleaned = _cleanup_query(query) or (query or "").strip()
    timeout = float(settings.RAG_REWRITE_TIMEOUT_SEC or 3.0)
    try:
        rewritten = await asyncio.wait_for(_llm_rewrite(query, db), timeout=timeout)
        return rewritten or cleaned
    except Exception as e:
        log.warning("query_rewrite_fallback: %s", e)
        return cleaned


async def expand_queries(query: str, db: AsyncSession) -> list[str]:
    if not settings.RAG_EXPAND_ENABLED:
        return []
    timeout = float(settings.RAG_REWRITE_TIMEOUT_SEC or 3.0)

    async def _call() -> list[str]:
        has_key = bool(
            settings.DASHSCOPE_API_KEY or settings.DEEPSEEK_API_KEY or settings.OPENAI_API_KEY
        )
        if not has_key:
            return []
        from app.core.llm.resolver import resolve_llm
        client, model = await resolve_llm(db, agent="planner")
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "列出最多 2 个同义检索短语，逗号分隔，不要解释。",
                },
                {"role": "user", "content": query},
            ],
            temperature=0.2,
            max_tokens=60,
        )
        raw = (resp.choices[0].message.content or "").strip()
        parts = [p.strip() for p in re.split(r"[,，;；]", raw) if p.strip()]
        return [p for p in parts if p != query][:2]

    try:
        return await asyncio.wait_for(_call(), timeout=timeout)
    except Exception as e:
        log.warning("query_expand_fallback: %s", e)
        return []


async def vector_search(
    db: AsyncSession,
    query_embedding: list[float],
    opportunity_id: uuid.UUID | None = None,
    top_k: int | None = None,
) -> list[dict]:
    top_k = top_k or settings.RERANK_TOP_K
    vec_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
    if opportunity_id:
        sql = text("""
            SELECT id, opportunity_id, activity_id, content, chunk_index, metadata,
                   1 - (embedding <=> CAST(:vec AS vector)) AS score
            FROM memory_chunks
            WHERE opportunity_id = CAST(:opp_id AS uuid)
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :top_k
        """)
        params = {"vec": vec_str, "opp_id": str(opportunity_id), "top_k": top_k}
    else:
        sql = text("""
            SELECT id, opportunity_id, activity_id, content, chunk_index, metadata,
                   1 - (embedding <=> CAST(:vec AS vector)) AS score
            FROM memory_chunks
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :top_k
        """)
        params = {"vec": vec_str, "top_k": top_k}
    result = await db.execute(sql, params)
    return [_row_to_hit(r) for r in result.fetchall()]


async def keyword_search(
    db: AsyncSession,
    query: str,
    opportunity_id: uuid.UUID | None = None,
    top_k: int | None = None,
) -> list[dict]:
    """pg_trgm + ILIKE；无扩展时回退纯 ILIKE。"""
    top_k = top_k or settings.RERANK_TOP_K
    tokens = _query_tokens(query)
    likes = [_escape_like(query)] + [_escape_like(t) for t in tokens]
    likes = likes[:6]
    like_clauses = " OR ".join(f"content ILIKE :like{i} ESCAPE '\\'" for i in range(len(likes)))
    params: dict = {"top_k": top_k, "q": query[:200]}
    for i, lk in enumerate(likes):
        params[f"like{i}"] = f"%{lk}%"
    opp_sql = ""
    if opportunity_id:
        opp_sql = "AND opportunity_id = CAST(:opp_id AS uuid)"
        params["opp_id"] = str(opportunity_id)
    where = f"WHERE ({like_clauses}) {opp_sql}" if like_clauses else f"WHERE false {opp_sql}"

    sql_trgm = text(f"""
        SELECT id, opportunity_id, activity_id, content, chunk_index, metadata,
               GREATEST(similarity(content, :q), 0.15) AS score
        FROM memory_chunks
        {where}
        ORDER BY score DESC
        LIMIT :top_k
    """)
    sql_like = text(f"""
        SELECT id, opportunity_id, activity_id, content, chunk_index, metadata,
               0.5 AS score
        FROM memory_chunks
        {where}
        LIMIT :top_k
    """)
    try:
        result = await db.execute(sql_trgm, params)
        rows = result.fetchall()
        hits = [_row_to_hit(r) for r in rows]
        if hits:
            return hits
    except Exception as e:
        log.debug("keyword_trgm_fallback: %s", e)
        try:
            await db.rollback()
        except Exception:
            pass
    try:
        result = await db.execute(sql_like, params)
        return [_row_to_hit(r) for r in result.fetchall()]
    except Exception as e:
        log.warning("keyword_search_failed: %s", e)
        try:
            await db.rollback()
        except Exception:
            pass
        return []


def keyword_search_memory(query: str, docs: list[dict], top_k: int = 20) -> list[dict]:
    """无 DB 的关键词召回（评测 / 单测）。"""
    qtok = tokenize(query)
    qlow = (query or "").lower()
    scored: list[tuple[float, dict]] = []
    for d in docs:
        content = d.get("content") or ""
        clow = content.lower()
        ov = len(qtok & tokenize(content)) / max(len(qtok), 1)
        substr = 0.4 if qlow and qlow in clow else 0.0
        for t in _query_tokens(query):
            if t.lower() in clow:
                substr = max(substr, 0.55)
        sc = ov + substr
        if sc > 0:
            row = dict(d)
            row["score"] = round(sc, 4)
            scored.append((sc, row))
    scored.sort(key=lambda x: -x[0])
    return [d for _, d in scored[:top_k]]


async def search_memory(
    db: AsyncSession,
    query: str,
    opportunity_id: uuid.UUID | None = None,
    return_n: int | None = None,
) -> list[dict]:
    return_n = return_n or settings.RERANK_RETURN_N
    top_k = settings.RERANK_TOP_K

    rewritten = await rewrite_query(query, db)
    variants = [rewritten]
    variants.extend(await expand_queries(rewritten, db))

    ranked: list[list[dict]] = []
    weights: list[float] = []
    for q in variants[:3]:
        try:
            embeddings = await embed_texts([q])
            ranked.append(await vector_search(db, embeddings[0], opportunity_id=opportunity_id, top_k=top_k))
            weights.append(float(settings.RAG_VECTOR_WEIGHT))
        except Exception as e:
            log.warning("vector_search_failed: %s", e)
            try:
                await db.rollback()
            except Exception:
                pass
        try:
            ranked.append(await keyword_search(db, q, opportunity_id=opportunity_id, top_k=top_k))
            weights.append(float(settings.RAG_KEYWORD_WEIGHT))
        except Exception as e:
            log.warning("keyword_search_failed: %s", e)
            try:
                await db.rollback()
            except Exception:
                pass

    fused = rrf_fuse(ranked, k=int(settings.RAG_RRF_K), weights=weights or None)
    fused = fused[:top_k]
    try:
        out = await rerank_docs(rewritten, fused, return_n)
    except Exception as e:
        log.warning("rerank_fallback: %s", e)
        out = fused[:return_n]
    for row in out:
        row.setdefault("score", row.get("rerank_score") or row.get("rrf_score") or 0)
        row["rewritten_query"] = rewritten
    return out
