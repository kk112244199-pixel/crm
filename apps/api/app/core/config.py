from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "MontoCRM"
    APP_ENV: Literal["development", "production", "test"] = "development"
    DEBUG: bool = False
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:80,https://localhost"
    RATE_LIMIT_ENABLED: bool = True
    # 开发/测试默认宽松，避免 E2E 误伤；生产请改为 5 / 10（Nginx 另有一层）
    RATE_LIMIT_AUTH_PER_MIN: int = 120
    RATE_LIMIT_EXTRACT_PER_MIN: int = 120

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://montocrm:changeme@localhost:5432/montocrm"

    # ── Redis / Celery ────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    @property
    def CELERY_BROKER_URL(self) -> str:
        return self.REDIS_URL

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return self.REDIS_URL

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 hours
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── LLM Providers ─────────────────────────────────────────────────────────
    LLM_AVAILABLE_PROVIDERS: str = "dashscope,deepseek,openai,mock"
    LLM_DEFAULT_PROVIDER: str = "dashscope"
    LLM_DEFAULT_MODEL: str = "qwen3.7-flash-2026-07-15"
    LLM_FALLBACK_PROVIDER: str = "deepseek"
    LLM_FALLBACK_MODEL: str = "deepseek-v4-flash"

    # Provider keys
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # Per-Agent defaults (DB overrides these at runtime)
    LLM_PLANNER_PROVIDER: str = "dashscope"
    LLM_PLANNER_MODEL: str = "qwen3.7-flash-2026-07-15"
    LLM_SYNTH_PROVIDER: str = "dashscope"
    LLM_SYNTH_MODEL: str = "qwen3.7-flash-2026-07-15"
    LLM_CUSTOMER_INSIGHT_PROVIDER: str = "dashscope"
    LLM_CUSTOMER_INSIGHT_MODEL: str = "qwen3.7-flash-2026-07-15"
    LLM_OPPORTUNITY_JUDGE_PROVIDER: str = "dashscope"
    LLM_OPPORTUNITY_JUDGE_MODEL: str = "qwen3.7-flash-2026-07-15"
    LLM_RISK_SENTINEL_PROVIDER: str = "dashscope"
    LLM_RISK_SENTINEL_MODEL: str = "qwen3.7-flash-2026-07-15"
    LLM_ACTION_PLANNER_PROVIDER: str = "dashscope"
    LLM_ACTION_PLANNER_MODEL: str = "qwen3.7-flash-2026-07-15"

    # ── Embedding ─────────────────────────────────────────────────────────────
    EMBEDDING_PROVIDER: str = "local"
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIMENSION: int = 1024

    # ── Rerank ────────────────────────────────────────────────────────────────
    RERANK_ENABLED: bool = True
    RERANK_PROVIDER: str = "local"
    RERANK_MODEL: str = "BAAI/bge-reranker-v2-m3"
    RERANK_TOP_K: int = 20
    RERANK_RETURN_N: int = 5

    # 本机 HF sidecar（torch 不进 API）。provider=sidecar 且服务可达时使用。
    HF_SIDECAR_URL: str = "http://127.0.0.1:18090"
    HF_SIDECAR_TIMEOUT_SEC: float = 60.0

    # ── LLM Guard ────────────────────────────────────────────────────────────
    GUARD_ENABLED: bool = True
    GUARD_MODE: Literal["rules", "hybrid", "llm-guard"] = "hybrid"
    GUARD_MAX_INPUT_CHARS: int = 10000
    GUARD_MAX_OUTPUT_CHARS: int = 8000
    GUARD_SENSITIVITY: float = 0.85
    GUARD_API_URL: str = ""

    # ── Hybrid RAG ────────────────────────────────────────────────────────────
    RAG_RRF_K: int = 60
    RAG_VECTOR_WEIGHT: float = 1.0
    RAG_KEYWORD_WEIGHT: float = 1.0
    RAG_REWRITE_TIMEOUT_SEC: float = 3.0
    RAG_EXPAND_ENABLED: bool = False

    # ── Langfuse ──────────────────────────────────────────────────────────────
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    RAGAS_BACKEND: Literal["heuristic", "llm"] = "heuristic"

    # ── 钉钉群自定义机器人 ─────────────────────────────────────────────────
    DINGTALK_ENABLED: bool = False
    DINGTALK_WEBHOOK_URL: str = ""
    DINGTALK_SECRET: str = ""
    DINGTALK_QUIET_START: str = "22:00"
    DINGTALK_QUIET_END: str = "08:00"
    DINGTALK_TZ: str = "Asia/Shanghai"
    APP_PUBLIC_BASE_URL: str = "http://localhost:3000"

    @field_validator("LLM_AVAILABLE_PROVIDERS", mode="before")
    @classmethod
    def _strip_providers(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def available_providers(self) -> list[str]:
        return [p.strip() for p in self.LLM_AVAILABLE_PROVIDERS.split(",") if p.strip()]


settings = Settings()
