.PHONY: eval test-guard test-rag hf-sidecar test-unit

eval:
	cd apps/api && python -m app.eval.runner --out tests/ragas_report.json

test-guard:
	cd apps/api && python -m pytest tests/test_guard_e2e.py tests/test_observability_p6.py -q

test-rag:
	cd apps/api && python -m pytest tests/test_rag_hybrid.py -q

test-unit:
	cd apps/api && python -m pytest -x -q tests/test_guard_e2e.py tests/test_dingtalk_notify.py tests/test_health_rules.py tests/test_rag_hybrid.py tests/test_observability_p6.py tests/test_security_p9.py

hf-sidecar:
	powershell -File scripts/run_hf_sidecar.ps1
