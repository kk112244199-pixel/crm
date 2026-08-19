"""
统一 LLM 调用工具 — 支持 JSON 结构化输出 + 重试 + Guard + 可观测性
"""
from __future__ import annotations
import json, re, time, uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.llm.resolver import resolve_llm
from app.services.guard import guard_input, guard_output, GuardViolation


async def call_llm_json(
    db: AsyncSession,
    agent: str,
    system_prompt: str,
    user_message: str,
    *,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    retries: int = 2,
) -> dict[str, Any]:
    """
    调用 LLM，要求 JSON 输出。
    - 自动 Guard 扫描 input/output
    - 解析失败时 JSON repair 重试
    - 返回解析后的 dict
    """
    # Guard input
    safe_msg = guard_input(user_message)

    client, model = await resolve_llm(db, agent=agent)

    # Resolve provider name for metrics
    provider = "unknown"
    try:
        from app.core.config import settings
        provider = settings.LLM_DEFAULT_PROVIDER
    except Exception:
        pass

    trace_id = str(uuid.uuid4())
    t_start = time.perf_counter()

    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": safe_msg},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},  # 支持的 Provider 使用 JSON mode
            )
            raw = resp.choices[0].message.content or ""
            guard_output(raw)
            latency_ms = (time.perf_counter() - t_start) * 1000
            _record_llm(agent, provider, model, latency_ms, len(safe_msg), len(raw), True, trace_id)
            try:
                from app.core.tracing import record_generation
                record_generation(
                    agent=agent, provider=provider, model=model,
                    latency_ms=latency_ms, input_text=safe_msg, output_text=raw,
                    success=True,
                )
            except Exception:
                pass
            return _parse_json(raw)
        except GuardViolation:
            raise
        except Exception as e:
            last_exc = e
            if attempt < retries:
                # 降级：不使用 JSON mode 重试
                try:
                    resp2 = await client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt + "\n\n必须输出纯 JSON，不要 markdown 代码块。"},
                            {"role": "user", "content": safe_msg},
                        ],
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    raw2 = resp2.choices[0].message.content or ""
                    return _parse_json(raw2)
                except Exception:
                    pass

    latency_ms = (time.perf_counter() - t_start) * 1000
    _record_llm(agent, provider, model, latency_ms, len(safe_msg), 0, False, trace_id, str(last_exc))
    try:
        from app.core.tracing import record_generation
        record_generation(
            agent=agent, provider=provider, model=model,
            latency_ms=latency_ms, input_text=safe_msg, output_text="",
            success=False, error=str(last_exc),
        )
    except Exception:
        pass
    raise RuntimeError(f"LLM call failed after {retries + 1} attempts: {last_exc}")


def _record_llm(agent, provider, model, latency_ms, in_chars, out_chars, ok, trace_id, error=None):
    try:
        from app.core.logging import log_llm_call
        from app.core.metrics import llm_requests_total, llm_latency_seconds
        log_llm_call(
            agent=agent, provider=provider, model=model,
            latency_ms=latency_ms, input_chars=in_chars, output_chars=out_chars,
            success=ok, error=error, trace_id=trace_id,
        )
        llm_requests_total.labels(agent=agent, provider=provider, model=model, status="ok" if ok else "error").inc()
        llm_latency_seconds.labels(agent=agent, provider=provider).observe(latency_ms / 1000)
    except Exception:
        pass  # Never let observability break the call path


def _parse_json(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response, stripping markdown fences."""
    # Remove ```json ... ``` fences
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    return json.loads(text)
