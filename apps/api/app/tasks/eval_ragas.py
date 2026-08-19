"""Weekly Ragas eval — Celery Beat Monday 00:00. Push stub until P8 DingTalk."""
from __future__ import annotations
import logging
from celery import shared_task

log = logging.getLogger("montocrm.eval.task")


@shared_task(name="app.tasks.eval_ragas.run_weekly_eval")
def run_weekly_eval() -> dict:
    from app.eval.runner import GOLDEN_DEFAULT, notify_eval_report, run
    from pathlib import Path
    out = Path("/tmp/ragas_report.json")
    try:
        report = run(GOLDEN_DEFAULT, out, None)
        notify_eval_report(report)
        return {"ok": True, "summary": report.get("summary"), "warnings": report.get("warnings")}
    except Exception as e:
        log.exception("weekly_eval_failed")
        return {"ok": False, "error": str(e)}
