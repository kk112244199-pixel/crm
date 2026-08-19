from math import nan

from app.eval.dashscope_ragas import as_text, finite_or_none, merge_ragas_into_summary
from app.eval.llm_judge import _clip01, _extract_json
from app.eval.ragas_compat import patch_langchain_vertex_stubs


def test_judge_json_extracts_fences():
    raw = '```json\n{"faithfulness": 1, "answer_relevancy": 0.5, "context_recall": 0}\n```'
    parsed = _extract_json(raw)
    assert _clip01(parsed["faithfulness"]) == 1.0
    assert _clip01(parsed["answer_relevancy"]) == 0.5


def test_ragas_compat_import():
    patch_langchain_vertex_stubs()
    from app.eval.ragas_compat import import_ragas_evaluate

    try:
        evaluate, *_ = import_ragas_evaluate()
    except ImportError:
        return
    assert callable(evaluate)


def test_as_text_coerces_non_str():
    assert as_text("hello") == "hello"
    assert as_text({"a": 1}) == '{"a": 1}'
    assert as_text("") == " "


def test_merge_ragas_overwrites_finite_only():
    report = {
        "summary": {"faithfulness": 0.96, "answer_relevancy": 0.84, "context_recall": 0.92},
        "warnings": [],
    }
    merge_ragas_into_summary(report, {"faithfulness": 0.61, "answer_relevancy": nan, "context_recall": 0.67})
    assert report["heuristic_summary"]["faithfulness"] == 0.96
    assert report["summary"]["faithfulness"] == 0.61
    assert report["summary"]["answer_relevancy"] == 0.84
    assert report["summary"]["context_recall"] == 0.67
    assert report["ragas_raw"]["answer_relevancy"] is None
    assert finite_or_none(nan) is None
def test_sidecar_embeddings_class_exists():
    from app.eval.dashscope_ragas import SidecarEmbeddings
    s = SidecarEmbeddings(base_url="http://127.0.0.1:18090")
    assert s.base_url.endswith("18090")
