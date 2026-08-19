"""P6 tracing mock + golden schema + ragas heuristic eval."""
from __future__ import annotations
import json
from pathlib import Path

from app.core.tracing import (
    agent_span,
    agent_trace,
    clear_mock_events,
    get_mock_events,
    record_generation,
)
from app.eval.runner import GOLDEN_DEFAULT, evaluate_dataset, load_golden, run


def test_langfuse_mock_exporter_records_trace_and_generation():
    clear_mock_events()
    with agent_trace(
        name="orchestrator",
        scene="meeting_extract",
        thread_id="t-1",
        user_id="u-1",
        opportunity_id="o-1",
    ):
        with agent_span("planner"):
            record_generation(
                agent="planner",
                provider="mock",
                model="mock-model",
                latency_ms=12.3,
                input_text="hello",
                output_text='{"ok":true}',
                success=True,
            )
        with agent_span("customer_insight"):
            pass
        with agent_span("synthesizer"):
            pass
    types = [e["type"] for e in get_mock_events()]
    assert "trace_start" in types
    assert "generation" in types
    gens = [e for e in get_mock_events() if e["type"] == "generation"]
    assert gens[0]["user_id"] == "u-1"
    assert gens[0]["opportunity_id"] == "o-1"
    assert gens[0]["input_sha256_16"]
    spans = {e["span"] for e in get_mock_events() if e["type"] == "span_end"}
    assert {"planner", "customer_insight", "synthesizer"} <= spans


def test_golden_schema():
    data = load_golden(GOLDEN_DEFAULT)
    assert data["version"]
    assert data["status"] in ("draft_pending_review", "frozen")
    assert len(data["items"]) == 10
    required_gt = {
        "answer",
        "competitor",
        "competitor_type",
        "amount",
        "decision_timing",
        "next_action",
        "champion",
        "economic_buyer",
        "pain_points",
        "risk_flags",
        "stakeholders",
        "evidence",
        "meddic_gaps",
        "confidence",
    }
    ids = []
    for item in data["items"]:
        assert item["id"]
        assert item["question"]
        assert item["canonical_text"]
        assert item["contexts"]
        assert item.get("meeting_date")
        gt = item["ground_truth"]
        assert required_gt <= set(gt.keys())
        assert isinstance(gt["stakeholders"], list)
        assert isinstance(gt["evidence"], list)
        assert gt["competitor_type"] in (
            "vendor", "build", "status_quo", "unspecified", "none",
        )
        ids.append(item["id"])
    assert len(set(ids)) == 10


def test_eval_report_has_ragas_metrics_and_does_not_block(tmp_path: Path):
    golden = load_golden(GOLDEN_DEFAULT)
    report = evaluate_dataset(golden)
    for k in ("faithfulness", "answer_relevancy", "context_recall"):
        assert k in report["summary"]
        assert 0.0 <= report["summary"][k] <= 1.0
    out = tmp_path / "ragas_report.json"
    again = run(GOLDEN_DEFAULT, out, None)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["n_items"] == 10
    assert saved["backend"] == "heuristic"
    assert again["summary"]["faithfulness"] >= 0.75
    assert again["summary"]["answer_relevancy"] >= 0.70
    assert saved["retrieval"]["mrr_at_5_hybrid"] >= 0.8
    assert saved["retrieval"]["relative_lift"] >= 0.2
