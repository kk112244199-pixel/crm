"""
LLM Guard — hybrid：规则/启发式评分 + 可选远程分类器；PII NER 脱敏。

用法：
    from app.services.guard import guard_input, guard_output, GuardViolation
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.services.guard_injection import (
    injection_score,
    output_leak_reason,
    http_classifier_score,
)
from app.services.guard_pii import redact_pii, find_pii, pii_labels_present


class GuardViolation(Exception):
    def __init__(
        self,
        reason: str,
        *,
        category: str = "injection",
        score: float = 1.0,
        evidence: str | None = None,
    ):
        super().__init__(f"Guard block: {reason}")
        self.reason = reason
        self.category = category
        self.score = score
        self.evidence = evidence


@dataclass
class GuardRuntime:
    enabled: bool = True
    mode: str = "hybrid"
    sensitivity: float = 0.85
    pii_redact_input: bool = False
    pii_redact_output: bool = True
    max_input_chars: int = 10000
    max_output_chars: int = 8000


_runtime = GuardRuntime()


def get_runtime() -> GuardRuntime:
    return _runtime


def apply_runtime(
    *,
    enabled: bool | None = None,
    mode: str | None = None,
    guard_config: dict | None = None,
    max_input: int | None = None,
    max_output: int | None = None,
) -> None:
    if enabled is not None:
        _runtime.enabled = enabled
    if mode:
        _runtime.mode = mode
    cfg = guard_config or {}
    if "sensitivity" in cfg:
        _runtime.sensitivity = float(cfg["sensitivity"])
    if "pii_redact_input" in cfg:
        _runtime.pii_redact_input = bool(cfg["pii_redact_input"])
    if "pii_redact_output" in cfg:
        _runtime.pii_redact_output = bool(cfg["pii_redact_output"])
    if max_input:
        _runtime.max_input_chars = max_input
    if max_output:
        _runtime.max_output_chars = max_output
    if "max_input_chars" in cfg:
        _runtime.max_input_chars = int(cfg["max_input_chars"])
    if "max_output_chars" in cfg:
        _runtime.max_output_chars = int(cfg["max_output_chars"])


def reset_runtime_from_env() -> None:
    apply_runtime(
        enabled=settings.GUARD_ENABLED,
        mode=settings.GUARD_MODE,
        guard_config={"sensitivity": settings.GUARD_SENSITIVITY},
        max_input=settings.GUARD_MAX_INPUT_CHARS,
        max_output=settings.GUARD_MAX_OUTPUT_CHARS,
    )


reset_runtime_from_env()


def apply_runtime_from_settings_row(row: Any) -> None:
    if row is None:
        reset_runtime_from_env()
        return
    apply_runtime(
        enabled=row.guard_enabled,
        mode=row.guard_mode,
        guard_config=row.guard_config,
    )


def _combined_injection_score(text: str) -> tuple[float, str | None]:
    local, reason = injection_score(text)
    mode = _runtime.mode
    if mode == "rules":
        return local, reason
    remote = http_classifier_score(text, settings.GUARD_API_URL)
    if remote is None:
        return local, reason
    if remote >= local:
        return remote, reason or "remote_classifier"
    return local, reason


def guard_input(text: str, *, redact_pii: bool | None = None) -> str:
    if not _runtime.enabled:
        return text
    if len(text) > _runtime.max_input_chars:
        raise GuardViolation(
            f"Input exceeds {_runtime.max_input_chars} chars (got {len(text)})",
            category="length",
        )
    score, why = _combined_injection_score(text)
    if score >= _runtime.sensitivity:
        raise GuardViolation(
            "Prompt injection detected",
            category="injection",
            score=score,
            evidence=why,
        )
    do_redact = _runtime.pii_redact_input if redact_pii is None else redact_pii
    if do_redact:
        return redact_pii(text)
    return text


def guard_output(text: str) -> str:
    if not _runtime.enabled:
        return text
    if len(text) > _runtime.max_output_chars:
        raise GuardViolation(
            f"Output exceeds {_runtime.max_output_chars} chars (got {len(text)})",
            category="length",
        )
    leak = output_leak_reason(text)
    if leak:
        raise GuardViolation(leak, category="output_leak", score=1.0)
    score, why = injection_score(text)
    if score >= _runtime.sensitivity:
        raise GuardViolation(
            "Prompt injection in model output",
            category="injection",
            score=score,
            evidence=why,
        )
    if _runtime.pii_redact_output:
        return redact_pii(text)
    return text


def scan_preview(text: str, direction: str = "input") -> dict:
    """Admin 样例测试，不抛异常。"""
    score, why = _combined_injection_score(text)
    labels = pii_labels_present(text)
    blocked = False
    category = None
    reason = None
    if len(text) > (
        _runtime.max_input_chars if direction == "input" else _runtime.max_output_chars
    ):
        blocked = True
        category = "length"
        reason = "too_long"
    elif score >= _runtime.sensitivity:
        blocked = True
        category = "injection"
        reason = why
    elif direction == "output" and output_leak_reason(text):
        blocked = True
        category = "output_leak"
        reason = output_leak_reason(text)
    redacted = redact_pii(text)
    return {
        "ok": not blocked,
        "blocked": blocked,
        "score": round(score, 3),
        "category": category,
        "reason": reason,
        "pii_labels": labels,
        "redacted_text": redacted,
        "sensitivity": _runtime.sensitivity,
        "mode": _runtime.mode,
    }


def increment_block_metric(category: str) -> None:
    try:
        from app.core.metrics import guard_blocked_total
        guard_blocked_total.labels(reason=category).inc()
    except Exception:
        pass


async def audit_guard_block(
    db,
    actor,
    *,
    endpoint: str,
    violation: GuardViolation,
    snippet: str,
    resource_id=None,
    opportunity_id=None,
) -> None:
    increment_block_metric(violation.category)
    try:
        from app.services.audit import write_audit
        safe_snip = redact_pii(snippet)[:200]
        await write_audit(
            db,
            actor=actor,
            action="guard.block",
            resource_type="guard",
            resource_id=resource_id,
            opportunity_id=opportunity_id,
            detail={
                "endpoint": endpoint,
                "category": violation.category,
                "reason": violation.reason,
                "score": violation.score,
                "evidence": violation.evidence,
                "snippet": safe_snip,
            },
        )
        await db.commit()
    except Exception:
        pass


def http_detail(violation: GuardViolation) -> dict:
    return {
        "code": "GUARD_BLOCKED",
        "reason": violation.reason,
        "category": violation.category,
        "score": violation.score,
    }


@dataclass
class GuardResult:
    ok: bool
    text: str
    violation: str | None = None
    extra: dict = field(default_factory=dict)
