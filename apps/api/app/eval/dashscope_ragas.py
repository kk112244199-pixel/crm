"""Dashscope adapters for ragas (string-only embeddings, Qwen without thinking)."""
from __future__ import annotations
import json
import math
from typing import Any


def as_text(value: Any) -> str:
    if isinstance(value, str):
        return value if value.strip() else " "
    if value is None:
        return " "
    return json.dumps(value, ensure_ascii=False)


def finite_or_none(value: Any) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return x


class SidecarEmbeddings:
    """本机 HF sidecar（BGE-M3），与 CRM 检索同一套向量。"""

    def __init__(self, *, base_url: str, timeout_sec: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    def embed_documents(self, texts: list[Any]) -> list[list[float]]:
        import httpx

        payload = [as_text(t) for t in texts]
        resp = httpx.post(
            f"{self.base_url}/embed",
            json={"texts": payload},
            timeout=self.timeout_sec,
        )
        resp.raise_for_status()
        embs = (resp.json() or {}).get("embeddings") or []
        if len(embs) != len(payload):
            raise RuntimeError(f"sidecar embed count {len(embs)} != {len(payload)}")
        return [[float(x) for x in row] for row in embs]

    def embed_query(self, text: Any) -> list[float]:
        return self.embed_documents([text])[0]

    async def aembed_documents(self, texts: list[Any]) -> list[list[float]]:
        return self.embed_documents(texts)

    async def aembed_query(self, text: Any) -> list[float]:
        return self.embed_query(text)


class DashscopeEmbeddings:
    """OpenAI SDK + 纯字符串 input。LangChain 默认会把文本编成 token id，Dashscope 会 400。"""

    def __init__(self, *, api_key: str, base_url: str, model: str = "text-embedding-v3"):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def embed_documents(self, texts: list[Any]) -> list[list[float]]:
        payload = [as_text(t) for t in texts]
        resp = self._client.embeddings.create(model=self.model, input=payload)
        return [row.embedding for row in resp.data]

    def embed_query(self, text: Any) -> list[float]:
        return self.embed_documents([text])[0]

    async def aembed_documents(self, texts: list[Any]) -> list[list[float]]:
        return self.embed_documents(texts)

    async def aembed_query(self, text: Any) -> list[float]:
        return self.embed_query(text)


def qwen_chat(*, api_key: str, base_url: str, model: str):
    """关闭 thinking，避免 ragas 要 n=3 时 Dashscope 报错。"""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0,
        extra_body={"enable_thinking": False},
        n=1,
        max_retries=2,
    )


def merge_ragas_into_summary(report: dict[str, Any], raw: dict[str, Any]) -> None:
    report["heuristic_summary"] = dict(report.get("summary") or {})
    cleaned = {str(k): finite_or_none(v) for k, v in raw.items()}
    report["ragas_raw"] = cleaned
    summary = report.setdefault("summary", {})
    for key in ("faithfulness", "answer_relevancy", "context_recall"):
        val = cleaned.get(key)
        if val is None:
            report.setdefault("warnings", []).append(
                f"ragas {key} is null; summary keeps heuristic {summary.get(key)}"
            )
            continue
        summary[key] = round(val, 4)
