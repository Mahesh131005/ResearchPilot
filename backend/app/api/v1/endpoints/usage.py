from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user, require_admin
from app.models.research import User
from app.services.usage_service import UsageService
from app.schemas.usage import (
    UsageLimits,
    UsageSummaryResponse,
    UsageHistoryResponse,
    AdminUsageSummaryResponse,
    AdminUsersUsageResponse,
)

router = APIRouter(tags=["usage"])

@router.get("/usage/me", response_model=UsageSummaryResponse)
async def get_my_usage(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the authenticated user's current rate limit quotas, daily and monthly jobs used,
    concurrency status, token usage breakdown, and reset timers.
    """
    return await UsageService.get_user_usage_summary(db, current_user)

@router.get("/usage/history", response_model=UsageHistoryResponse)
async def get_my_usage_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    provider: Optional[str] = Query(None, description="Filter by provider ('gemini' or 'tavily')"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns paginated usage events (tokens, embeddings, web searches) strictly isolated to the user.
    """
    return await UsageService.get_user_usage_history(
        db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        provider=provider,
    )

@router.get("/usage/limits", response_model=UsageLimits)
async def get_my_limits(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns effective rate limits and quotas for the user based on their tier and custom overrides.
    """
    return await UsageService.get_user_limits(db, current_user)

# --------------------------------------------------------------------------
# Admin Endpoints (Restricted to role == 'admin')
# --------------------------------------------------------------------------

@router.get("/admin/usage", response_model=AdminUsageSummaryResponse)
async def get_platform_usage_admin(
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    (Admin only) Aggregates platform-wide token consumption, search counts, and job volumes across all users.
    """
    return await UsageService.get_admin_usage_summary(db)

@router.get("/admin/usage/users", response_model=AdminUsersUsageResponse)
async def get_users_usage_admin(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    (Admin only) Returns per-user usage breakdown across registered users.
    """
    return await UsageService.get_admin_users_usage(db, page=page, page_size=page_size)

