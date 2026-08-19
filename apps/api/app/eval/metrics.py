"""Ragas-compatible 启发式指标（无 LLM / 无 ragas 包时 CI 可跑）。"""
from __future__ import annotations
import re
from typing import Any

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


def _overlap(a: set[str], b: set[str]) -> float:
    if not a:
        return 1.0
    if not b:
        return 0.0
    return len(a & b) / len(a)


def flatten_facts(ground_truth: dict[str, Any]) -> list[str]:
    facts: list[str] = []
    for key in (
        "answer",
        "competitor",
        "decision_timing",
        "next_action",
        "pain_points",
    ):
        val = ground_truth.get(key)
        if val:
            facts.append(str(val))
    # 仅当已确认时才把角色当事实（null / 空字符串不进入召回）
    for key in ("champion", "economic_buyer"):
        val = ground_truth.get(key)
        if val:
            facts.append(str(val))
    amount = ground_truth.get("amount")
    if isinstance(amount, dict) and amount.get("value") is not None:
        facts.append(str(amount["value"]))
    elif isinstance(amount, (int, float)):
        facts.append(str(amount))
    for flag in ground_truth.get("risk_flags") or []:
        facts.append(str(flag))
    return facts


def split_claims(text: str) -> list[str]:
    parts = re.split(r"[；;。！？\n]", text or "")
    return [p.strip() for p in parts if len(p.strip()) >= 4]


def score_item(
    *,
    question: str,
    answer: str,
    contexts: list[str],
    ground_truth: dict[str, Any],
) -> dict[str, float]:
    ctx = "\n".join(contexts)
    ctx_tok = tokenize(ctx)
    ans_tok = tokenize(answer)
    q_tok = tokenize(question)
    gt_ans = str(ground_truth.get("answer") or "")
    gt_tok = tokenize(gt_ans)

    claims = split_claims(answer)
    if not claims:
        faith = 0.0
    else:
        supported = 0
        for c in claims:
            ct = tokenize(c)
            if (
                c in ctx
                or _overlap(ct, ctx_tok) >= 0.2
                or len(ct & ctx_tok) >= 2
            ):
                supported += 1
        faith = supported / len(claims)

    facts = flatten_facts(ground_truth)
    fact_in_ctx = 0
    for f in facts:
        ft = tokenize(f)
        if not ft:
            continue
        if f in ctx or _overlap(ft, ctx_tok) >= 0.4:
            fact_in_ctx += 1
    n = max(len(facts), 1)
    context_recall = fact_in_ctx / n
    answer_relevancy = (
        0.2 * _overlap(q_tok, ans_tok) + 0.8 * _overlap(gt_tok, ans_tok)
        if (gt_tok or q_tok)
        else 0.0
    )
    return {
        "faithfulness": round(faith, 4),
        "answer_relevancy": round(answer_relevancy, 4),
        "context_recall": round(context_recall, 4),
    }


def aggregate(scores: list[dict[str, float]]) -> dict[str, float]:
    if not scores:
        return {"faithfulness": 0.0, "answer_relevancy": 0.0, "context_recall": 0.0}
    keys = ("faithfulness", "answer_relevancy", "context_recall")
    return {k: round(sum(float(s[k]) for s in scores) / len(scores), 4) for k in keys}
