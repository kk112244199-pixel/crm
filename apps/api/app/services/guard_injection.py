"""
Prompt injection scoring — 规则 + 变体（Base64 / 中英混写）+ 可选 HTTP 分类器降级。
"""
from __future__ import annotations
import base64
import re
import binascii

_INJECTION_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"ignore\s+(previous|all|above|prior)\s+(instructions|prompts|rules)", re.I), 1.0),
    (re.compile(r"forget\s+(your|all)\s+(training|instructions|rules)", re.I), 1.0),
    (re.compile(r"\bDAN\s+mode\b", re.I), 1.0),
    (re.compile(r"\bjailbreak\b", re.I), 1.0),
    (re.compile(r"do\s+anything\s+now", re.I), 1.0),
    (re.compile(r"override\s+(safety|the\s+system|guardrails)", re.I), 0.95),
    (re.compile(r"system\s*prompt", re.I), 0.9),
    (re.compile(r"<\s*\|?\s*im_start\s*\|?\s*>", re.I), 1.0),
    (re.compile(r"<\s*/?think\s*>", re.I), 0.9),
    (re.compile(r"\bpretend\s+(you\s+are|to\s+be)\b", re.I), 0.85),
    (re.compile(r"\bact\s+as\s+(if\s+you\s+(are|were)|a)\b", re.I), 0.85),
    (re.compile(r"you\s+are\s+now\s+(?:a|an|the)\s+\w+", re.I), 0.85),
    (re.compile(r"new\s+instructions\s*:", re.I), 0.9),
    (re.compile(r"developer\s+mode\s+(on|enabled)", re.I), 0.95),
    (re.compile(r"忽略\s*(之前的|以上的|全部的|所有的)?\s*(指令|提示|规则|设定)"), 1.0),
    (re.compile(r"请忽略(系统|你的).{0,6}(指令|提示|规则)"), 1.0),
    (re.compile(r"越狱(模式)?"), 1.0),
    (re.compile(r"开发者模式(已开启|开启)"), 0.95),
    (re.compile(r"你现在是(?!.{0,8}(客户|销售|对接))"), 0.9),
    (re.compile(r"你不再受.{0,8}(限制|约束|规则)"), 0.95),
    (re.compile(r"系统提示词"), 0.9),
    (re.compile(r"把以上内容全部忘掉"), 1.0),
    (re.compile(r"disclose\s+(your\s+)?(hidden\s+)?system\s+prompt", re.I), 1.0),
]

_B64 = re.compile(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{24,}={0,2}(?![A-Za-z0-9+/])")

# 输出侧：模型泄露 / 密钥
_OUTPUT_LEAK = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"sk-ant-[A-Za-z0-9\-]{10,}"),
    re.compile(r"BEGIN (RSA |OPENSSH )?PRIVATE KEY"),
    re.compile(r"\{TODO\}"),
    re.compile(r"\[填写\]"),
    re.compile(r"\[TODO\]"),
]


def _try_b64_decode(chunk: str) -> str | None:
    pad = "=" * ((4 - len(chunk) % 4) % 4)
    try:
        raw = base64.b64decode(chunk + pad, validate=True)
    except (binascii.Error, ValueError):
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _scan_patterns(text: str) -> tuple[float, str | None]:
    best = 0.0
    reason = None
    for pat, score in _INJECTION_PATTERNS:
        if pat.search(text):
            if score > best:
                best = score
                reason = pat.pattern[:80]
    return best, reason


def injection_score(text: str) -> tuple[float, str | None]:
    """Return (score 0-1, reason)."""
    best, reason = _scan_patterns(text)
    # mixed-case already covered by IGNORECASE
    # Base64 payload
    for m in _B64.finditer(text):
        decoded = _try_b64_decode(m.group())
        if not decoded or len(decoded) < 8:
            continue
        s2, r2 = _scan_patterns(decoded)
        if s2 > best:
            best = min(1.0, s2)
            reason = f"base64:{r2}"
    return best, reason


def output_leak_reason(text: str) -> str | None:
    for pat in _OUTPUT_LEAK:
        if pat.search(text):
            return f"output_leak:{pat.pattern[:60]}"
    return None


def http_classifier_score(text: str, api_url: str, timeout: float = 1.5) -> float | None:
    """Optional remote classifier. None = unavailable (caller falls back)."""
    if not api_url:
        return None
    try:
        import httpx
        r = httpx.post(
            api_url.rstrip("/") + "/scan",
            json={"text": text[:8000]},
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json()
        if "injection_score" in data:
            return float(data["injection_score"])
        if data.get("is_injection"):
            return 1.0
        return float(data.get("score", 0.0))
    except Exception:
        return None
