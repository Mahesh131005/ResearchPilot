import uuid
from decimal import Decimal
from typing import Optional, Dict, Any
from sqlalchemy import String, Integer, ForeignKey, JSON, Boolean, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base, TimestampMixin

class UserQuota(Base, TimestampMixin):
    """
    Per-user quota overrides. If a user does not have an explicit row,
    default limits from their User.tier (e.g. 'free') are applied.
    """
    __tablename__ = "user_quotas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    hourly_submissions_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    daily_jobs_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    monthly_jobs_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    concurrent_jobs_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tavily_searches_per_job_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    user = relationship("User", backref="custom_quota")


class ProviderUsageEvent(Base, TimestampMixin):
    """
    Granular, idempotent tracking of every provider call (Gemini LLM, Gemini Embedding, Tavily Search).
    Distinguishes actual metadata from estimated values.
    """
    __tablename__ = "provider_usage_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # "gemini", "tavily"
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # "llm_generation", "structured_generation", "embedding", "web_search"
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Token metrics (Gemini)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    embedding_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Search metrics (Tavily)
    request_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    search_depth: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Cost metrics (Stage 6)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0.000000"), nullable=False)
    pricing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("provider_pricing.id", ondelete="SET NULL"), nullable=True
    )

    # Metadata & Idempotency
    is_estimated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    usage_metadata_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)
    meta_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    user = relationship("User", backref="usage_events")
    job = relationship("ResearchJob", backref="usage_events")

