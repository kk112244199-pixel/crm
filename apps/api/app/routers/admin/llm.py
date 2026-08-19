"""
Admin LLM 设置 API
GET  /admin/llm/options   → 可选 Provider 列表（仅已配 Key）
GET  /admin/llm/settings  → 当前设置
PUT  /admin/llm/settings  → 更新设置
POST /admin/llm/test      → 连通性测试
"""
import time
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.llm.resolver import _build_client
from app.core.security.deps import RequireAdmin, CurrentUser
from app.db.session import get_db
from app.models.llm_settings import LLMSettings
from app.schemas.llm import (
    LLMSettingsOut, LLMSettingsUpdate, LLMTestRequest, LLMTestResponse, ProviderOption,
    GuardConfig, GuardTestRequest, GuardTestResponse,
)
from app.services.guard import (
    apply_runtime_from_settings_row,
    scan_preview,
)

router = APIRouter(prefix="/admin/llm", tags=["Admin LLM"])

# Known model catalog per provider (whitelist for Admin UI)
_MODEL_CATALOG: dict[str, list[str]] = {
    "dashscope": [
        "qwen3.7-flash-2026-07-15",
        "qwen-max",
        "qwen-plus",
        "qwen-turbo",
    ],
    "deepseek": [
        "deepseek-v4-flash",
        "deepseek-chat",
        "deepseek-reasoner",
    ],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
    ],
    "mock": ["mock-model"],
}


def _has_key(provider: str) -> bool:
    """Check if API key is configured for provider."""
    key_map = {
        "dashscope": settings.DASHSCOPE_API_KEY,
        "deepseek": settings.DEEPSEEK_API_KEY,
        "openai": settings.OPENAI_API_KEY,
        "mock": "mock",
    }
    return bool(key_map.get(provider))


@router.get("/options", response_model=list[ProviderOption])
async def get_llm_options(
    _: Annotated[None, RequireAdmin],
):
    """返回白名单内且已配 Key 的 Provider，不含 Key 值。"""
    options = []
    for provider in settings.available_providers:
        if _has_key(provider):
            options.append(ProviderOption(
                provider=provider,
                models=_MODEL_CATALOG.get(provider, []),
                is_default=(provider == settings.LLM_DEFAULT_PROVIDER),
            ))
    return options


@router.get("/settings", response_model=LLMSettingsOut)
async def get_settings(
    _: Annotated[None, RequireAdmin],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(LLMSettings).limit(1))
    row = result.scalar_one_or_none()
    if not row:
        # Return ENV defaults when DB not yet configured
        return LLMSettingsOut(
            default_provider=settings.LLM_DEFAULT_PROVIDER,
            default_model=settings.LLM_DEFAULT_MODEL,
            fallback_provider=settings.LLM_FALLBACK_PROVIDER,
            fallback_model=settings.LLM_FALLBACK_MODEL,
            embedding_provider=settings.EMBEDDING_PROVIDER,
            embedding_model=settings.EMBEDDING_MODEL,
            embedding_dimension=settings.EMBEDDING_DIMENSION,
            rerank_enabled=settings.RERANK_ENABLED,
            rerank_provider=settings.RERANK_PROVIDER,
            rerank_model=settings.RERANK_MODEL,
            rerank_top_k=settings.RERANK_TOP_K,
            rerank_return_n=settings.RERANK_RETURN_N,
            guard_enabled=settings.GUARD_ENABLED,
            guard_mode=settings.GUARD_MODE,
            guard_config=GuardConfig(sensitivity=settings.GUARD_SENSITIVITY),
        )
    return row


@router.put("/settings", response_model=LLMSettingsOut)
async def upsert_settings(
    body: LLMSettingsUpdate,
    _: Annotated[None, RequireAdmin],
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Validate provider is in whitelist
    allowed = settings.available_providers
    for p in [body.default_provider, body.fallback_provider]:
        if p not in allowed:
            raise HTTPException(400, detail=f"Provider '{p}' not in whitelist")
    if body.guard_mode not in ("rules", "hybrid", "llm-guard"):
        raise HTTPException(400, detail="Invalid guard_mode")

    result = await db.execute(select(LLMSettings).limit(1))
    row = result.scalar_one_or_none()
    old_emb = None
    if row:
        old_emb = (row.embedding_provider, row.embedding_model, row.embedding_dimension)

    data = body.model_dump(exclude={"change_note"})
    # Serialize agent_overrides (nested pydantic → dict)
    if body.agent_overrides:
        data["agent_overrides"] = {
            k: v.model_dump() for k, v in body.agent_overrides.items()
        }
    if body.guard_config:
        data["guard_config"] = body.guard_config.model_dump()

    if row:
        for k, v in data.items():
            setattr(row, k, v)
        row.updated_by = current_user.id
        row.change_note = body.change_note
    else:
        row = LLMSettings(**data, updated_by=current_user.id, change_note=body.change_note)
        db.add(row)

    await db.commit()
    await db.refresh(row)
    apply_runtime_from_settings_row(row)
    new_emb = (row.embedding_provider, row.embedding_model, row.embedding_dimension)
    if old_emb and old_emb != new_emb:
        from app.services.rag.reindex_status import mark_needs_reindex
        mark_needs_reindex("embedding_changed")
    return row


@router.post("/guard/test", response_model=GuardTestResponse)
async def test_guard(
    body: GuardTestRequest,
    _: Annotated[None, RequireAdmin],
):
    if body.direction not in ("input", "output"):
        raise HTTPException(400, detail="direction must be input or output")
    result = scan_preview(body.text, direction=body.direction)
    return GuardTestResponse(**result)


@router.post("/test", response_model=LLMTestResponse)
async def test_connection(
    body: LLMTestRequest,
    _: Annotated[None, RequireAdmin],
):
    """向指定 Provider 发送最小 ping，返回 latency_ms。不消耗 token（用 max_tokens=1）。"""
    if body.provider not in settings.available_providers:
        raise HTTPException(400, detail="Provider not in whitelist")
    if not _has_key(body.provider):
        raise HTTPException(400, detail="API key not configured for this provider")

    try:
        client = _build_client(body.provider)
        start = time.monotonic()
        resp = await client.chat.completions.create(
            model=body.model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        return LLMTestResponse(ok=True, latency_ms=latency_ms, message="OK")
    except Exception as e:
        return LLMTestResponse(ok=False, latency_ms=0, message=str(e))
