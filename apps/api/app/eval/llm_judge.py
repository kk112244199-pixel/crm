"""Dashscope-compatible LLM judge used when ragas evaluate cannot run."""
from __future__ import annotations
import json
import re
from typing import Any

_SYS = (
    "You score RAG answers. Reply with JSON only: "
    '{"faithfulness":0-1,"answer_relevancy":0-1,"context_recall":0-1}. '
    "faithfulness: claims in the answer are supported by contexts. "
    "answer_relevancy: answer addresses the question. "
    "context_recall: contexts cover the ground-truth answer."
)


def _extract_json(raw: str) -> dict[str, Any]:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def _clip01(v: Any) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, x))


def score_item_with_openai(client: Any, model: str, item: dict[str, Any]) -> dict[str, float]:
    gt = item.get("ground_truth") or {}
    contexts = item.get("contexts") or [item.get("canonical_text") or ""]
    user = json.dumps(
        {
            "question": item.get("question", ""),
            "answer": gt.get("answer", ""),
            "contexts": contexts[:4],
            "ground_truth": gt.get("answer", ""),
        },
        ensure_ascii=False,
    )[:8000]
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYS},
            {"role": "user", "content": user},
        ],
        temperature=0,
        max_tokens=200,
    )
    parsed = _extract_json(resp.choices[0].message.content or "{}")
    return {
        "faithfulness": _clip01(parsed.get("faithfulness")),
        "answer_relevancy": _clip01(parsed.get("answer_relevancy")),
        "context_recall": _clip01(parsed.get("context_recall")),
    }


def judge_golden(golden: dict[str, Any], *, api_key: str, base_url: str, model: str) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)
    rows = []
    for item in golden.get("items") or []:
        scores = score_item_with_openai(client, model, item)
        rows.append({"id": item.get("id"), **scores})
    n = max(len(rows), 1)
    summary = {
        k: round(sum(r[k] for r in rows) / n, 4)
        for k in ("faithfulness", "answer_relevancy", "context_recall")
    }
    return {"summary": summary, "items": rows}
