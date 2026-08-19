"""
Embedding 服务。
- dashscope / openai：远程 API
- local / mock：确定性 hash ngram 向量（无 Key 也可做混合检索评测；生产请切 dashscope/BGE）
"""
from __future__ import annotations
import hashlib
import math

from app.core.config import settings
from app.services.rag.textutil import tokenize
import logging

log = logging.getLogger("montocrm.embedder")


def hash_embed(text: str, dim: int) -> list[float]:
    vec = [0.0] * dim
    t = text or ""
    n = max(len(t) - 1, 0)
    for i in range(n):
        ng = t[i : i + 2].encode("utf-8")
        h = hashlib.blake2b(ng, digest_size=8).digest()
        bucket = int.from_bytes(h, "little") % dim
        sign = 1.0 if h[0] & 1 else -1.0
        vec[bucket] += sign
    for tok in tokenize(t):
        h = hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(h, "little") % dim
        vec[bucket] += 2.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    provider = (settings.EMBEDDING_PROVIDER or "local").lower()
    dim = settings.EMBEDDING_DIMENSION

    if provider in ("mock", "local", "hash"):
        return [hash_embed(t, dim) for t in texts]
    if provider in ("sidecar", "hf", "huggingface"):
        from app.services.rag.sidecar import sidecar_embed
        remote = await sidecar_embed(texts)
        if remote is not None:
            return remote
        log.warning("sidecar_embed_fallback_hash")
        return [hash_embed(t, dim) for t in texts]
    if provider == "dashscope":
        return await _embed_dashscope(texts, dim)
    if provider == "openai":
        return await _embed_openai(texts, dim)
    return [hash_embed(t, dim) for t in texts]


async def _embed_dashscope(texts: list[str], dim: int) -> list[list[float]]:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.DASHSCOPE_BASE_URL,
    )
    resp = await client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=texts,
    )
    return [e.embedding for e in resp.data]


async def _embed_openai(texts: list[str], dim: int) -> list[list[float]]:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    resp = await client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=texts,
    )
    return [e.embedding for e in resp.data]
