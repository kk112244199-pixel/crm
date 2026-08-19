"""
Langfuse 适配层。

有 LANGFUSE_PUBLIC_KEY + SECRET 时走官方 SDK；否则写入内存 Mock（CI / 无账号不红）。
观测失败永不打断业务。
"""
from __future__ import annotations
import hashlib
import logging
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Iterator

_log = logging.getLogger("montocrm.trace")

_MAX_EVENTS = 500
_events: list[dict[str, Any]] = []

_current_trace_id: ContextVar[str | None] = ContextVar("crm_trace_id", default=None)
_current_meta: ContextVar[dict[str, Any]] = ContextVar("crm_trace_meta", default={})


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _record(event: dict[str, Any]) -> None:
    _events.append(event)
    if len(_events) > _MAX_EVENTS:
        del _events[: len(_events) - _MAX_EVENTS]


def clear_mock_events() -> None:
    _events.clear()


def get_mock_events() -> list[dict[str, Any]]:
    return list(_events)


def current_trace_id() -> str | None:
    return _current_trace_id.get()


def _langfuse_client():
    try:
        from app.core.config import settings
        pk = settings.LANGFUSE_PUBLIC_KEY
        sk = settings.LANGFUSE_SECRET_KEY
        if not pk or not sk:
            return None
        from langfuse import Langfuse
        return Langfuse(
            public_key=pk,
            secret_key=sk,
            host=settings.LANGFUSE_HOST or "https://cloud.langfuse.com",
        )
    except Exception as e:
        _log.debug("langfuse_client_unavailable", extra={"error": str(e)})
        return None


@dataclass
class _LiveTrace:
    id: str
    lf_trace: Any = None
    spans: dict[str, Any] = field(default_factory=dict)


_live: ContextVar[_LiveTrace | None] = ContextVar("crm_live_trace", default=None)


@contextmanager
def agent_trace(
    *,
    name: str = "orchestrator",
    scene: str = "",
    thread_id: str | None = None,
    user_id: str | None = None,
    opportunity_id: str | None = None,
    tags: list[str] | None = None,
) -> Iterator[str]:
    trace_id = thread_id or str(uuid.uuid4())
    meta = {
        "scene": scene,
        "user_id": user_id,
        "opportunity_id": opportunity_id,
        "tags": tags or [],
    }
    tok_id = _current_trace_id.set(trace_id)
    tok_meta = _current_meta.set(meta)
    lf_trace = None
    client = _langfuse_client()
    try:
        if client is not None:
            lf_trace = client.trace(
                id=trace_id,
                name=name,
                user_id=user_id,
                session_id=trace_id,
                metadata={"opportunity_id": opportunity_id, "scene": scene},
                tags=tags or [scene] if scene else None,
            )
    except Exception:
        lf_trace = None
    live_tok = _live.set(_LiveTrace(id=trace_id, lf_trace=lf_trace))
    _record({"type": "trace_start", "trace_id": trace_id, "name": name, **meta})
    t0 = time.perf_counter()
    try:
        yield trace_id
    except Exception as e:
        _record({"type": "trace_error", "trace_id": trace_id, "error": str(e)})
        raise
    finally:
        latency_ms = (time.perf_counter() - t0) * 1000
        _record({"type": "trace_end", "trace_id": trace_id, "name": name, "latency_ms": round(latency_ms, 1)})
        try:
            if client is not None:
                client.flush()
        except Exception:
            pass
        _current_trace_id.reset(tok_id)
        _current_meta.reset(tok_meta)
        _live.reset(live_tok)


@contextmanager
def agent_span(name: str, *, input_text: str | None = None) -> Iterator[None]:
    trace_id = _current_trace_id.get() or str(uuid.uuid4())
    t0 = time.perf_counter()
    lf_span = None
    live = _live.get()
    try:
        if live and live.lf_trace is not None:
            lf_span = live.lf_trace.span(
                name=name,
                input={"sha256_16": _sha(input_text or ""), "chars": len(input_text or "")},
            )
            live.spans[name] = lf_span
    except Exception:
        lf_span = None
    _record({"type": "span_start", "trace_id": trace_id, "span": name})
    err = None
    try:
        yield
    except Exception as e:
        err = str(e)
        raise
    finally:
        latency_ms = (time.perf_counter() - t0) * 1000
        _record({
            "type": "span_end",
            "trace_id": trace_id,
            "span": name,
            "latency_ms": round(latency_ms, 1),
            "error": err,
        })
        try:
            if lf_span is not None:
                lf_span.end(metadata={"latency_ms": round(latency_ms, 1), "error": err})
        except Exception:
            pass


def record_generation(
    *,
    agent: str,
    provider: str,
    model: str,
    latency_ms: float,
    input_text: str,
    output_text: str,
    success: bool,
    error: str | None = None,
) -> None:
    trace_id = _current_trace_id.get()
    meta = _current_meta.get() or {}
    event = {
        "type": "generation",
        "trace_id": trace_id,
        "agent": agent,
        "provider": provider,
        "model": model,
        "latency_ms": round(latency_ms, 1),
        "input_sha256_16": _sha(input_text),
        "output_sha256_16": _sha(output_text) if output_text else None,
        "input_chars": len(input_text),
        "output_chars": len(output_text or ""),
        "success": success,
        "error": error,
        "user_id": meta.get("user_id"),
        "opportunity_id": meta.get("opportunity_id"),
    }
    _record(event)
    live = _live.get()
    try:
        if live and live.lf_trace is not None:
            live.lf_trace.generation(
                name=agent,
                model=model,
                input={"sha256_16": event["input_sha256_16"], "chars": event["input_chars"]},
                output={"sha256_16": event["output_sha256_16"], "chars": event["output_chars"]},
                metadata={
                    "provider": provider,
                    "latency_ms": event["latency_ms"],
                    "success": success,
                    "opportunity_id": meta.get("opportunity_id"),
                    "user_id": meta.get("user_id"),
                },
                level="ERROR" if not success else "DEFAULT",
                status_message=error,
            )
    except Exception:
        pass


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
    """兼容 P4 stub 签名。"""
    _record({
        "type": "agent_trace",
        "trace_id": trace_id,
        "agent": agent,
        "scene": scene,
        "latency_ms": round(latency_ms, 1),
        "model": model,
        "input_sha256_16": _sha(input_text),
        "output_keys": list(output.keys()) if isinstance(output, dict) else [],
        "tags": tags or [],
    })
    _log.info(
        "agent_trace",
        extra={
            "event": "agent_trace",
            "trace_id": trace_id,
            "agent": agent,
            "scene": scene,
            "latency_ms": round(latency_ms, 1),
            "model": model,
        },
    )
