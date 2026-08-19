"""RRF 融合与轻量分词（中文 bigram + 英文词）。"""
from __future__ import annotations
import re

_TOKEN = re.compile(r"[\u4e00-\u9fff]+|[A-Za-z0-9.]+")


def tokenize(text: str) -> set[str]:
    tokens: set[str] = set()
    for t in _TOKEN.findall(text or ""):
        tl = t.lower()
        if re.fullmatch(r"[a-z0-9.]+", tl):
            if len(tl) > 1:
                tokens.add(tl)
            continue
        if len(tl) <= 2:
            if len(tl) > 1:
                tokens.add(tl)
            continue
        for i in range(len(tl) - 1):
            tokens.add(tl[i : i + 2])
    return tokens


def rrf_fuse(
    ranked_lists: list[list[dict]],
    *,
    k: int = 60,
    weights: list[float] | None = None,
) -> list[dict]:
    """Reciprocal Rank Fusion. Each item needs chunk_id."""
    weights = weights or [1.0] * len(ranked_lists)
    scores: dict[str, float] = {}
    payload: dict[str, dict] = {}
    for w, lst in zip(weights, ranked_lists):
        for rank, item in enumerate(lst, start=1):
            cid = item.get("chunk_id") or item.get("id")
            if not cid:
                continue
            scores[cid] = scores.get(cid, 0.0) + w / (k + rank)
            payload[cid] = item
    ordered = sorted(scores.items(), key=lambda x: -x[1])
    out = []
    for cid, sc in ordered:
        row = dict(payload[cid])
        row["rrf_score"] = round(sc, 6)
        out.append(row)
    return out
