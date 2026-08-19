"""
LLM Resolver — 优先级：DB llm_settings > ENV > hardcoded defaults

用法：
    client, model = await resolve_llm(db, agent="planner")
    response = await client.chat.completions.create(model=model, messages=[...])
"""
from __future__ import annotations
from typing import Literal

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.llm_settings import LLMSettings

# 每个 Agent 对应的 ENV 配置键前缀
_AGENT_ENV_MAP: dict[str, tuple[str, str]] = {
    "planner":          (settings.LLM_PLANNER_PROVIDER,          settings.LLM_PLANNER_MODEL),
    "synth":            (settings.LLM_SYNTH_PROVIDER,             settings.LLM_SYNTH_MODEL),
    "customer_insight": (settings.LLM_CUSTOMER_INSIGHT_PROVIDER,  settings.LLM_CUSTOMER_INSIGHT_MODEL),
    "opportunity_judge":(settings.LLM_OPPORTUNITY_JUDGE_PROVIDER, settings.LLM_OPPORTUNITY_JUDGE_MODEL),
    "risk_sentinel":    (settings.LLM_RISK_SENTINEL_PROVIDER,     settings.LLM_RISK_SENTINEL_MODEL),
    "action_planner":   (settings.LLM_ACTION_PLANNER_PROVIDER,    settings.LLM_ACTION_PLANNER_MODEL),
}

_PROVIDER_CLIENT_CACHE: dict[str, AsyncOpenAI] = {}


def _build_client(provider: str) -> AsyncOpenAI:
    if provider in _PROVIDER_CLIENT_CACHE:
        return _PROVIDER_CLIENT_CACHE[provider]

    if provider == "dashscope":
        client = AsyncOpenAI(
            api_key=settings.DASHSCOPE_API_KEY or "placeholder",
            base_url=settings.DASHSCOPE_BASE_URL,
        )
    elif provider == "deepseek":
        client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY or "placeholder",
            base_url=settings.DEEPSEEK_BASE_URL,
        )
    elif provider == "openai":
        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY or "placeholder",
            base_url=settings.OPENAI_BASE_URL,
        )
    elif provider == "mock":
        # 测试用 — MockOpenAI 不发网络请求，直接返回固定 JSON
        from app.core.llm.mock_client import MockOpenAI
        client = MockOpenAI()  # type: ignore[assignment]
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")

    _PROVIDER_CLIENT_CACHE[provider] = client
    return client


async def resolve_llm(
    db: AsyncSession,
    agent: str = "default",
) -> tuple[AsyncOpenAI, str]:
    """
    返回 (AsyncOpenAI client, model_name)
    优先级: DB override > ENV > global default
    """
    # 1. 读 DB singleton
    result = await db.execute(select(LLMSettings).limit(1))
    db_settings = result.scalar_one_or_none()

    provider: str | None = None
    model: str | None = None

    if db_settings:
        overrides: dict = db_settings.agent_overrides or {}
        if agent in overrides:
            provider = overrides[agent].get("provider")
            model = overrides[agent].get("model")
        if not provider:
            provider = db_settings.default_provider
            model = db_settings.default_model

    # 2. Fallback to ENV
    if not provider:
        env_pair = _AGENT_ENV_MAP.get(agent)
        if env_pair:
            provider, model = env_pair
        else:
            provider = settings.LLM_DEFAULT_PROVIDER
            model = settings.LLM_DEFAULT_MODEL

    # 3. Build client; on failure use fallback
    try:
        client = _build_client(provider)
    except ValueError:
        provider = settings.LLM_FALLBACK_PROVIDER
        model = settings.LLM_FALLBACK_MODEL
        client = _build_client(provider)

    return client, model  # type: ignore[return-value]
