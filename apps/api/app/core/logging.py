"""
结构化日志 — JSON format，含 provider/model/agent_name/latency_ms
所有 Agent 调用通过 log_llm_call() 统一记录
"""
from __future__ import annotations
import json
import logging
import sys
import time
import uuid
from contextlib import contextmanager
from typing import Any

# ── JSON Formatter ────────────────────────────────────────────────────────────

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log: dict[str, Any] = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Merge extra fields
        for key, val in record.__dict__.items():
            if key not in ("msg", "args", "levelname", "levelno", "pathname",
                           "filename", "module", "exc_info", "exc_text",
                           "stack_info", "lineno", "funcName", "created",
                           "msecs", "relativeCreated", "thread", "threadName",
                           "processName", "process", "name", "message"):
                log[key] = val

        if record.exc_info:
            log["exc"] = self.formatException(record.exc_info)

        return json.dumps(log, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    # Silence noisy libs
    for lib in ("uvicorn.access", "sqlalchemy.engine", "httpx"):
        logging.getLogger(lib).setLevel(logging.WARNING)


# ── LLM call logger ───────────────────────────────────────────────────────────

_log = logging.getLogger("montocrm.llm")


def log_llm_call(
    *,
    agent: str,
    provider: str,
    model: str,
    latency_ms: float,
    input_chars: int,
    output_chars: int,
    success: bool,
    error: str | None = None,
    trace_id: str | None = None,
) -> None:
    _log.info(
        "llm_call",
        extra={
            "event": "llm_call",
            "agent": agent,
            "provider": provider,
            "model": model,
            "latency_ms": round(latency_ms, 1),
            "input_chars": input_chars,
            "output_chars": output_chars,
            "success": success,
            "error": error,
            "trace_id": trace_id or str(uuid.uuid4()),
        },
    )


def trace_agent_run(
    *,
    trace_id: str,
    agent: str,
    scene: str,
    input_text: str,
    output: dict,
    latency_ms: float,
    model: str,
    tags: list[str] | None = None,
) -> None:
    from app.core.tracing import trace_agent_run as _tr
    _tr(
        trace_id=trace_id,
        agent=agent,
        scene=scene,
        input_text=input_text,
        output=output,
        latency_ms=latency_ms,
        model=model,
        tags=tags,
    )


@contextmanager
def timed_span(label: str):
    """Simple timing context manager."""
    t0 = time.perf_counter()
    try:
        yield
    finally:
        elapsed = (time.perf_counter() - t0) * 1000
        logging.getLogger("montocrm.perf").debug(
            label,
            extra={"event": "span", "label": label, "latency_ms": round(elapsed, 1)},
        )
