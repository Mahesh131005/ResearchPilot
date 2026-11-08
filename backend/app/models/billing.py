import uuid
import datetime
from typing import Optional, Dict, Any
from decimal import Decimal
from sqlalchemy import String, Integer, Numeric, ForeignKey, JSON, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base, TimestampMixin

class ProviderPricing(Base, TimestampMixin):
    """
    Versioned, configurable provider pricing definitions.
    Prevents hardcoded pricing assumptions and allows rates to be updated over time.
    """
    __tablename__ = "provider_pricing"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # "gemini", "tavily"
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # "llm_generation", "structured_generation", "embedding", "web_search"
    unit_type: Mapped[str] = mapped_column(String(50), default="per_1m_tokens", nullable=False) # "per_1k_tokens", "per_1m_tokens", "per_request"

    # Rates in USD
    input_rate_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0.000000"), nullable=False)
    output_rate_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0.000000"), nullable=False)
    fixed_request_rate_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0.000000"), nullable=False)

    effective_from: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False
    )
    effective_to: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class UserWallet(Base, TimestampMixin):
    """
    User credit balance and reservation wallet.
    Supports atomic budget reservations, preventing concurrent research jobs
    from double-spending the same remaining balance.
    """
    __tablename__ = "user_wallets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    balance_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("1.0000"), nullable=False
    )
    reserved_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0.0000"), nullable=False
    )
    lifetime_spent_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0.0000"), nullable=False
    )
    monthly_budget_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    auto_recharge: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    user = relationship("User", backref="wallet")


class CostLedgerEntry(Base, TimestampMixin):
    """
    Immutable audit ledger for all financial movements.
    Records every reservation, settlement, refund, credit grant, and Stripe payment.
    """
    __tablename__ = "cost_ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    entry_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    ) # "credit_grant", "reservation_hold", "reservation_refund", "job_settlement", "stripe_payment", "admin_adjustment"
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    balance_before_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    balance_after_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    reserved_before_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    reserved_after_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    meta_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    user = relationship("User", backref="ledger_entries")
    job = relationship("ResearchJob", backref="ledger_entries")

