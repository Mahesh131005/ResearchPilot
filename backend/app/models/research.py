import uuid
import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy import String, Text, ForeignKey, JSON, Float, Boolean, DateTime, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base, TimestampMixin

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="user", nullable=False) # 'user' or 'admin'
    tier: Mapped[str] = mapped_column(String(50), default="free", nullable=False) # 'free', 'pro', etc.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    research_jobs: Mapped[List["ResearchJob"]] = relationship(
        "ResearchJob", back_populates="user"
    )
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )

class RefreshToken(Base, TimestampMixin):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_token_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")

class ResearchJob(Base, TimestampMixin):
    __tablename__ = "research_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    client_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    depth: Mapped[str] = mapped_column(String(50), default="standard", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False, index=True)
    cost_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    budget_reserved_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 6), nullable=True)
    plan: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped[Optional["User"]] = relationship("User", back_populates="research_jobs")
    sources: Mapped[List["ResearchSource"]] = relationship(
        "ResearchSource", back_populates="job", cascade="all, delete-orphan"
    )
    reports: Mapped[List["ResearchReport"]] = relationship(
        "ResearchReport", back_populates="job", cascade="all, delete-orphan"
    )
    events: Mapped[List["ResearchEvent"]] = relationship(
        "ResearchEvent", back_populates="job", cascade="all, delete-orphan"
    )

class ResearchSource(Base, TimestampMixin):
    __tablename__ = "research_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False) # 'web' or 'document'
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    page_number: Mapped[Optional[int]] = mapped_column(nullable=True)
    snippet: Mapped[str] = mapped_column(Text, nullable=False)

    job: Mapped["ResearchJob"] = relationship("ResearchJob", back_populates="sources")

class ResearchReport(Base, TimestampMixin):
    __tablename__ = "research_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False) # structured sections

    job: Mapped["ResearchJob"] = relationship("ResearchJob", back_populates="reports")
    claims: Mapped[List["ReportClaim"]] = relationship(
        "ReportClaim", back_populates="report", cascade="all, delete-orphan"
    )

class ReportClaim(Base, TimestampMixin):
    __tablename__ = "report_claims"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(50), nullable=False
    ) # 'supported', 'partially_supported', 'unsupported', 'contradictory'
    evidence_quote: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    citation_source: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    report: Mapped["ResearchReport"] = relationship("ResearchReport", back_populates="claims")

class ResearchEvent(Base, TimestampMixin):
    __tablename__ = "research_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    job: Mapped["ResearchJob"] = relationship("ResearchJob", back_populates="events")

