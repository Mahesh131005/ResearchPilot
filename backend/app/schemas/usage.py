import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class UsageLimits(BaseModel):
    tier: str
    hourly_submissions_limit: int
    daily_jobs_limit: int
    monthly_jobs_limit: int
    concurrent_jobs_limit: int
    tavily_searches_per_job_limit: int

class GeminiUsageBreakdown(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    embedding_tokens: int = 0
    request_count: int = 0
    has_estimated_usage: bool = False

class TavilyUsageBreakdown(BaseModel):
    search_count: int = 0

class UsageSummaryResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    tier: str
    limits: UsageLimits
    hourly_submissions_used: int
    daily_jobs_used: int
    daily_jobs_remaining: int
    monthly_jobs_used: int
    monthly_jobs_remaining: int
    concurrent_jobs_active: int
    gemini_usage: GeminiUsageBreakdown
    tavily_usage: TavilyUsageBreakdown
    daily_reset_utc: datetime
    monthly_reset_utc: datetime

class ProviderUsageEventResponse(BaseModel):
    id: uuid.UUID
    job_id: Optional[uuid.UUID] = None
    provider: str
    operation_type: str
    model_name: Optional[str] = None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    embedding_tokens: int
    request_count: int
    search_depth: Optional[str] = None
    is_estimated: bool
    usage_metadata_available: bool
    created_at: datetime

    model_config = {"from_attributes": True}

class UsageHistoryResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[ProviderUsageEventResponse]

class AdminUsageSummaryResponse(BaseModel):
    total_users: int
    total_jobs: int
    jobs_by_status: Dict[str, int]
    gemini_total_tokens: int
    gemini_input_tokens: int
    gemini_output_tokens: int
    gemini_embedding_tokens: int
    tavily_total_searches: int
    total_events_recorded: int

class AdminUserUsageItem(BaseModel):
    user_id: uuid.UUID
    email: str
    name: Optional[str] = None
    tier: str
    role: str
    is_active: bool
    active_jobs: int
    jobs_today: int
    jobs_this_month: int
    total_jobs: int
    total_tokens: int
    total_searches: int

class AdminUsersUsageResponse(BaseModel):
    total: int
    items: List[AdminUserUsageItem]

