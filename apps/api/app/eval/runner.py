"""
Ragas 评估入口。

默认 backend=heuristic（无 Key 可跑）。
RAGAS_BACKEND=llm 且已安装 ragas 时走 LLM 评测（失败则降级 heuristic，不阻断）。

用法：
  python -m app.eval.runner
  python -m app.eval.runner --out tests/ragas_report.json
"""
from __future__ import annotations
import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ENV = Path(__file__).resolve().parents[4] / ".env"
_API_ENV = Path(__file__).resolve().parents[2] / ".env"
try:
    from dotenv import load_dotenv
    if _REPO_ENV.exists():
        load_dotenv(_REPO_ENV, override=False)
    if _API_ENV.exists():
        load_dotenv(_API_ENV, override=False)
except Exception:
    pass

from app.eval.metrics import aggregate, score_item

log = logging.getLogger("montocrm.eval")

GOLDEN_DEFAULT = Path(__file__).resolve().parents[2] / "tests" / "golden" / "extract_writeback.json"
THRESHOLDS = {"faithfulness": 0.75, "answer_relevancy": 0.70}


def load_golden(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("items"), list):
        raise ValueError("golden JSON 缺少 items[]")
    return data


def load_predictions(path: Path | None) -> dict[str, str]:
    if not path or not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "predictions" in raw:
        raw = raw["predictions"]
    return {str(k): str(v) for k, v in raw.items()}


def evaluate_dataset(golden: dict[str, Any], predictions: dict[str, str] | None = None) -> dict[str, Any]:
    predictions = predictions or {}
    rows = []
    for item in golden["items"]:
        iid = item["id"]
        gt = item["ground_truth"]
        contexts = list(item.get("contexts") or [])
        if item.get("canonical_text"):
            contexts = [item["canonical_text"], *contexts]
        answer = predictions.get(iid) or gt.get("answer", "")
        scores = score_item(
            question=item.get("question", ""),
            answer=answer,
            contexts=contexts,
            ground_truth=gt,
        )
        rows.append({"id": iid, **scores})
    summary = aggregate(rows)
    warnings = []
    for metric, thresh in THRESHOLDS.items():
        if summary.get(metric, 0) < thresh:
            warnings.append(f"{metric}={summary[metric]} < {thresh} (warning, not blocking)")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "backend": "heuristic",
        "golden_version": golden.get("version"),
        "golden_status": golden.get("status"),
        "n_items": len(rows),
        "summary": summary,
        "thresholds": THRESHOLDS,
        "warnings": warnings,
        "items": rows,
    }


def _dashscope_llm():
    from app.core.config import settings
    from app.eval.dashscope_ragas import qwen_chat

    key = settings.DASHSCOPE_API_KEY or settings.OPENAI_API_KEY
    base = settings.DASHSCOPE_BASE_URL if settings.DASHSCOPE_API_KEY else settings.OPENAI_BASE_URL
    if not key:
        return None
    return qwen_chat(api_key=key, base_url=base, model=settings.LLM_DEFAULT_MODEL)


def _ragas_embeddings():
    """优先 BGE sidecar（与检索一致）；不可达时用 Dashscope text-embedding-v3。"""
    import httpx
    from app.core.config import settings
    from app.eval.dashscope_ragas import DashscopeEmbeddings, SidecarEmbeddings

    base = (settings.HF_SIDECAR_URL or "").rstrip("/")
    if base:
        try:
            health = httpx.get(f"{base}/health", timeout=3.0)
            if health.status_code == 200:
                return SidecarEmbeddings(
                    base_url=base,
                    timeout_sec=float(settings.HF_SIDECAR_TIMEOUT_SEC or 120),
                )
        except Exception:
            pass
    key = settings.DASHSCOPE_API_KEY or settings.OPENAI_API_KEY
    url = settings.DASHSCOPE_BASE_URL if settings.DASHSCOPE_API_KEY else settings.OPENAI_BASE_URL
    if not key:
        return None
    return DashscopeEmbeddings(api_key=key, base_url=url, model="text-embedding-v3")


def _inject_openai_compat_env() -> None:
    """ragas / openai SDK 会读 OPENAI_*；空字符串也会挡住 setdefault。"""
    import os
    from app.core.config import settings

    key = settings.DASHSCOPE_API_KEY or settings.OPENAI_API_KEY
    if not key:
        return
    os.environ["OPENAI_API_KEY"] = key
    os.environ["OPENAI_BASE_URL"] = (
        settings.DASHSCOPE_BASE_URL if settings.DASHSCOPE_API_KEY else settings.OPENAI_BASE_URL
    )


def maybe_llm_ragas(report: dict[str, Any], golden: dict[str, Any]) -> dict[str, Any]:
    """Optional LLM eval; never raises out. Prefer ragas, else Dashscope JSON judge."""
    try:
        from app.core.config import settings
        if getattr(settings, "RAGAS_BACKEND", "heuristic") != "llm":
            return report
    except Exception:
        return report

    try:
        _inject_openai_compat_env()
        from datasets import Dataset
        from app.eval.ragas_compat import import_ragas_evaluate

        evaluate, faithfulness, answer_relevancy, context_recall = import_ragas_evaluate()
        records = []
        for item in golden["items"]:
            gt = item["ground_truth"]
            records.append({
                "user_input": item["question"],
                "response": gt.get("answer", ""),
                "retrieved_contexts": item.get("contexts") or [item.get("canonical_text", "")],
                "reference": gt.get("answer", ""),
            })
        ds = Dataset.from_list(records)
        kwargs: dict[str, Any] = {
            "metrics": [faithfulness, answer_relevancy, context_recall],
            "raise_exceptions": False,
            "show_progress": False,
        }
        llm = _dashscope_llm()
        if llm is not None:
            kwargs["llm"] = llm
        emb = _ragas_embeddings()
        if emb is not None:
            kwargs["embeddings"] = emb
        result = evaluate(ds, **kwargs)
        report["backend"] = "ragas_llm"
        raw: dict[str, Any] = {}
        if hasattr(result, "to_pandas"):
            means = result.to_pandas().mean(numeric_only=True)
            raw = {str(k): v for k, v in means.items()}
        else:
            raw = {k: v for k, v in dict(result).items()}
        from app.eval.dashscope_ragas import merge_ragas_into_summary
        merge_ragas_into_summary(report, raw)
        return report
    except Exception as e:
        report["warnings"].append(f"ragas evaluate failed, trying llm_judge: {e}")

    try:
        from app.core.config import settings
        from app.eval.llm_judge import judge_golden

        key = settings.DASHSCOPE_API_KEY or settings.OPENAI_API_KEY
        base = (
            settings.DASHSCOPE_BASE_URL
            if settings.DASHSCOPE_API_KEY
            else settings.OPENAI_BASE_URL
        )
        if not key:
            report["warnings"].append("llm_judge skipped: no DASHSCOPE_API_KEY / OPENAI_API_KEY")
            return report
        judged = judge_golden(
            golden,
            api_key=key,
            base_url=base,
            model=settings.LLM_DEFAULT_MODEL,
        )
        report["backend"] = "llm_judge"
        report["llm_judge"] = judged
        report["summary"] = judged["summary"]
        id_scores = {r["id"]: r for r in judged["items"]}
        for row in report.get("items") or []:
            extra = id_scores.get(row.get("id"))
            if extra:
                row["llm_faithfulness"] = extra["faithfulness"]
                row["llm_answer_relevancy"] = extra["answer_relevancy"]
                row["llm_context_recall"] = extra["context_recall"]
    except Exception as e:
        report["warnings"].append(f"llm_judge failed, kept heuristic: {e}")
    return report


def run(golden_path: Path, out_path: Path | None, predictions_path: Path | None = None) -> dict[str, Any]:
    golden = load_golden(golden_path)
    preds = load_predictions(predictions_path)
    report = evaluate_dataset(golden, preds)
    try:
        from app.eval.retrieval import evaluate_retrieval
        report["retrieval"] = evaluate_retrieval(golden)
    except Exception as e:
        report.setdefault("warnings", []).append(f"retrieval eval skipped: {e}")
    report = maybe_llm_ragas(report, golden)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    return report


def notify_eval_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") or {}
    retrieval = report.get("retrieval") or {}
    log.info(
        "ragas_eval_done",
        extra={"event": "ragas_eval", "summary": summary, "warnings": report.get("warnings")},
    )
    try:
        from app.core.redis_compat import apply_redis_resp2
        apply_redis_resp2()
        from app.services.dingtalk import enqueue_dingtalk
        warnings = "; ".join(report.get("warnings") or []) or "无"
        enqueue_dingtalk("ragas_weekly", {
            "faithfulness": summary.get("faithfulness"),
            "answer_relevancy": summary.get("answer_relevancy"),
            "context_recall": summary.get("context_recall"),
            "n_items": report.get("n_items"),
            "retrieval_mrr": (retrieval or {}).get("mrr_at_5_hybrid", "—"),
            "warnings": warnings,
        })
    except Exception as e:
        log.warning("dingtalk_eval_enqueue_failed: %s", e)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser(description="MontoCRM Ragas-style eval")
    p.add_argument("--golden", type=Path, default=GOLDEN_DEFAULT)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--predictions", type=Path, default=None)
    args = p.parse_args(argv)
    out = args.out or (Path(__file__).resolve().parents[2] / "tests" / "ragas_report.json")
    report = run(args.golden, out, args.predictions)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    if report.get("retrieval"):
        print(json.dumps(report["retrieval"], ensure_ascii=False, indent=2))
    for w in report["warnings"]:
        print(f"WARNING: {w}", file=sys.stderr)
    notify_eval_report(report)
    return 0  # 警告不阻断


if __name__ == "__main__":
    raise SystemExit(main())
