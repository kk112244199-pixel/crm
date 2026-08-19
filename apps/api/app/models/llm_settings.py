import uuid
from sqlalchemy import String, Boolean, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class LLMSettings(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Admin 在 UI 保存的 LLM 全局设置，运行时优先级高于 ENV。
    每次 PUT /admin/llm/settings 做 upsert（保持单行 singleton）。
    """
    __tablename__ = "llm_settings"

    # Chat 全局默认
    default_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    default_model: Mapped[str] = mapped_column(String(100), nullable=False)
    fallback_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    fallback_model: Mapped[str] = mapped_column(String(100), nullable=False)

    # 按 Agent 覆盖 {"planner": {"provider": "dashscope", "model": "..."}, ...}
    agent_overrides: Mapped[dict | None] = mapped_column(JSONB)

    # Embedding
    embedding_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, default=1024)

    # Rerank
    rerank_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    rerank_provider: Mapped[str | None] = mapped_column(String(50))
    rerank_model: Mapped[str | None] = mapped_column(String(100))
    rerank_top_k: Mapped[int] = mapped_column(Integer, default=20)
    rerank_return_n: Mapped[int] = mapped_column(Integer, default=5)

    # Guard
    guard_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    guard_mode: Mapped[str] = mapped_column(String(20), default="rules")
    guard_config: Mapped[dict | None] = mapped_column(JSONB)

    # Audit
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    change_note: Mapped[str | None] = mapped_column(Text)
    notify_config: Mapped[dict | None] = mapped_column(JSONB)
