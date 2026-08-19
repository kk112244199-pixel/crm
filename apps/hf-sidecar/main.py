"""
本地 HuggingFace RAG sidecar（torch 只活在这里，不进 API 镜像）。

启动（Windows）：
  $env:HF_HOME='D:\\huggingface_cache'
  $env:HF_HUB_OFFLINE='1'
  cd apps/hf-sidecar
  pip install -r requirements.txt
  python -m uvicorn main:app --host 127.0.0.1 --port 18090
"""
from __future__ import annotations
import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger("montocrm.hf_sidecar")
logging.basicConfig(level=logging.INFO)

HF_HOME = os.environ.get("HF_HOME") or os.environ.get("HUGGINGFACE_HUB_CACHE") or r"D:\huggingface_cache"
os.environ.setdefault("HF_HOME", HF_HOME)
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", HF_HOME)

EMBED_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3")
RERANK_MODEL = os.environ.get("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")

app = FastAPI(title="MontoCRM HF sidecar", version="1.0.0")

_embedder = None
_reranker = None
_device = "cpu"


def _pick_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


class EmbedRequest(BaseModel):
    texts: list[str] = Field(default_factory=list)


class RerankRequest(BaseModel):
    query: str
    documents: list[str] = Field(default_factory=list)
    top_n: int = 5


def _load_embedder():
    global _embedder, _device
    if _embedder is not None:
        return _embedder
    _device = _pick_device()
    log.info("loading embedder %s device=%s hf_home=%s", EMBED_MODEL, _device, HF_HOME)
    from sentence_transformers import SentenceTransformer
    _embedder = SentenceTransformer(EMBED_MODEL, device=_device)
    return _embedder


def _load_reranker():
    global _reranker, _device
    if _reranker is not None:
        return _reranker
    _device = _pick_device()
    log.info("loading reranker %s device=%s", RERANK_MODEL, _device)
    from sentence_transformers import CrossEncoder
    _reranker = CrossEncoder(
        RERANK_MODEL,
        device=_device,
        max_length=512,
        trust_remote_code=True,
    )
    return _reranker


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "hf_home": HF_HOME,
        "device": _pick_device(),
        "embed_model": EMBED_MODEL,
        "rerank_model": RERANK_MODEL,
        "embedder_loaded": _embedder is not None,
        "reranker_loaded": _reranker is not None,
    }


@app.post("/embed")
def embed(req: EmbedRequest) -> dict[str, Any]:
    if not req.texts:
        return {"embeddings": [], "dim": 0, "model": EMBED_MODEL}
    try:
        model = _load_embedder()
        vecs = model.encode(
            req.texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        out = [v.tolist() for v in vecs]
        dim = len(out[0]) if out else 0
        return {"embeddings": out, "dim": dim, "model": EMBED_MODEL}
    except Exception as e:
        log.exception("embed_failed")
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.post("/rerank")
def rerank(req: RerankRequest) -> dict[str, Any]:
    if not req.documents:
        return {"results": []}
    try:
        model = _load_reranker()
        pairs = [(req.query, (d or "")[:4000]) for d in req.documents]
        scores = model.predict(pairs, show_progress_bar=False)
        ranked = sorted(
            enumerate(float(s) for s in scores),
            key=lambda x: -x[1],
        )
        top_n = max(int(req.top_n), 0)
        results = [{"index": i, "score": sc} for i, sc in ranked[:top_n]]
        return {"results": results, "model": RERANK_MODEL}
    except Exception as e:
        log.exception("rerank_failed")
        raise HTTPException(status_code=503, detail=str(e)) from e
