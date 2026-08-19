from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class GuardConfig(BaseModel):
    sensitivity: float = Field(default=0.85, ge=0.0, le=1.0)
    pii_redact_input: bool = False
    pii_redact_output: bool = True
    max_input_chars: int = 10000
    max_output_chars: int = 8000


class ProviderOption(BaseModel):
    provider: str
    models: list[str]
    is_default: bool = False


class AgentOverride(BaseModel):
    provider: str
    model: str


class LLMSettingsUpdate(BaseModel):
    default_provider: str
    default_model: str
    fallback_provider: str
    fallback_model: str
    agent_overrides: Optional[dict[str, AgentOverride]] = None
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int = 1024
    rerank_enabled: bool = True
    rerank_provider: Optional[str] = None
    rerank_model: Optional[str] = None
    rerank_top_k: int = 20
    rerank_return_n: int = 5
    guard_enabled: bool = True
    guard_mode: str = "hybrid"
    guard_config: Optional[GuardConfig] = None
    change_note: Optional[str] = None


class LLMSettingsOut(LLMSettingsUpdate):
    model_config = ConfigDict(from_attributes=True)
    # API key fields are never returned


class GuardTestRequest(BaseModel):
    text: str
    direction: str = "input"  # input | output


class GuardTestResponse(BaseModel):
    ok: bool
    blocked: bool
    score: float
    category: Optional[str] = None
    reason: Optional[str] = None
    pii_labels: list[str] = []
    redacted_text: str
    sensitivity: float
    mode: str


class LLMTestRequest(BaseModel):
    provider: str
    model: str


class LLMTestResponse(BaseModel):
    ok: bool
    latency_ms: int
    message: str
