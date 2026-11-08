import uuid
import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_

from app.core.config import settings
from app.core.usage_context import get_usage_context
from app.db.session import AsyncSessionLocal
from app.models.research import User, ResearchJob
from app.models.usage import UserQuota, ProviderUsageEvent
from app.schemas.usage import (
    UsageLimits,
    GeminiUsageBreakdown,
    TavilyUsageBreakdown,
    UsageSummaryResponse,
    ProviderUsageEventResponse,
    UsageHistoryResponse,
    AdminUsageSummaryResponse,
    AdminUserUsageItem,
    AdminUsersUsageResponse,
)

class UsageService:
    @staticmethod
    async def get_user_limits(db: AsyncSession, user: User) -> UsageLimits:
        """Retrieves effective quota limits for a user, applying custom overrides if present."""
        tier_defaults = settings.get_tier_limits(user.tier)

        stmt = select(UserQuota).where(UserQuota.user_id == user.id)
        res = await db.execute(stmt)
        custom = res.scalar_one_or_none()

        return UsageLimits(
            tier=user.tier,
            hourly_submissions_limit=(
                custom.hourly_submissions_limit
                if custom and custom.hourly_submissions_limit is not None
                else tier_defaults["hourly_submissions"]
            ),
            daily_jobs_limit=(
                custom.daily_jobs_limit
                if custom and custom.daily_jobs_limit is not None
                else tier_defaults["daily_jobs"]
            ),
            monthly_jobs_limit=(
                custom.monthly_jobs_limit
                if custom and custom.monthly_jobs_limit is not None
                else tier_defaults["monthly_jobs"]
            ),
            concurrent_jobs_limit=(
                custom.concurrent_jobs_limit
                if custom and custom.concurrent_jobs_limit is not None
                else tier_defaults["concurrent_jobs"]
            ),
            tavily_searches_per_job_limit=(
                custom.tavily_searches_per_job_limit
                if custom and custom.tavily_searches_per_job_limit is not None
                else tier_defaults["tavily_searches_per_job"]
            ),
        )

    @staticmethod
    async def record_usage_event(
        db: AsyncSession,
        user_id: uuid.UUID,
        provider: str,
        operation_type: str,
        job_id: Optional[uuid.UUID] = None,
        model_name: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        embedding_tokens: int = 0,
        request_count: int = 1,
        search_depth: Optional[str] = None,
        is_estimated: bool = False,
        usage_metadata_available: bool = True,
        idempotency_key: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> ProviderUsageEvent:
        """Records a granular provider usage event with idempotency verification."""
        if idempotency_key:
            stmt = select(ProviderUsageEvent).where(
                ProviderUsageEvent.idempotency_key == idempotency_key
            )
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                return existing

        event = ProviderUsageEvent(
            id=uuid.uuid4(),
            user_id=user_id,
            job_id=job_id,
            provider=provider,
            operation_type=operation_type,
            model_name=model_name,
            input_tokens=max(0, input_tokens),
            output_tokens=max(0, output_tokens),
            total_tokens=max(0, total_tokens),
            embedding_tokens=max(0, embedding_tokens),
            request_count=max(1, request_count),
            search_depth=search_depth,
            is_estimated=is_estimated,
            usage_metadata_available=usage_metadata_available,
            idempotency_key=idempotency_key,
            meta_info=meta_info,
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event

    @staticmethod
    async def record_from_context(
        provider: str,
        operation_type: str,
        model_name: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        embedding_tokens: int = 0,
        request_count: int = 1,
        search_depth: Optional[str] = None,
        is_estimated: bool = False,
        usage_metadata_available: bool = True,
        idempotency_key: Optional[str] = None,
        meta_info: Optional[Dict[str, Any]] = None,
    ) -> Optional[ProviderUsageEvent]:
        """Automatically records usage for the active task/request usage context if present."""
        ctx = get_usage_context()
        if not ctx or not ctx.get("user_id"):
            return None
        try:
            async with AsyncSessionLocal() as session:
                return await UsageService.record_usage_event(
                    db=session,
                    user_id=ctx["user_id"],
                    job_id=ctx.get("job_id"),
                    provider=provider,
                    operation_type=operation_type,
                    model_name=model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    embedding_tokens=embedding_tokens,
                    request_count=request_count,
                    search_depth=search_depth,
                    is_estimated=is_estimated,
                    usage_metadata_available=usage_metadata_available,
                    idempotency_key=idempotency_key,
                    meta_info=meta_info,
                )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Error recording usage event from context: {e}")
            return None

    @staticmethod
    async def get_user_usage_summary(db: AsyncSession, user: User) -> UsageSummaryResponse:
        """Aggregates active quota usage and token/search consumption for the authenticated user."""
        limits = await UsageService.get_user_limits(db, user)

        now = datetime.datetime.now(datetime.timezone.utc)
        one_hour_ago = now - datetime.timedelta(hours=1)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_midnight = start_of_day + datetime.timedelta(days=1)

        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            next_month = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

        # 1. Hourly jobs
        hourly_q = select(func.count()).select_from(ResearchJob).where(
            ResearchJob.user_id == user.id,
            ResearchJob.created_at >= one_hour_ago,
        )
        hourly_used = (await db.execute(hourly_q)).scalar() or 0

        # 2. Daily jobs
        daily_q = select(func.count()).select_from(ResearchJob).where(
            ResearchJob.user_id == user.id,
            ResearchJob.created_at >= start_of_day,
            ResearchJob.status != "failed",
        )
        daily_used = (await db.execute(daily_q)).scalar() or 0
        daily_remaining = max(0, limits.daily_jobs_limit - daily_used)

        # 3. Monthly jobs
        monthly_q = select(func.count()).select_from(ResearchJob).where(
            ResearchJob.user_id == user.id,
            ResearchJob.created_at >= start_of_month,
            ResearchJob.status != "failed",
        )
        monthly_used = (await db.execute(monthly_q)).scalar() or 0
        monthly_remaining = max(0, limits.monthly_jobs_limit - monthly_used)

        # 4. Concurrent jobs
        concurrent_q = select(func.count()).select_from(ResearchJob).where(
            ResearchJob.user_id == user.id,
            ResearchJob.status.in_(["queued", "processing"]),
        )
        concurrent_active = (await db.execute(concurrent_q)).scalar() or 0

        # 5. Gemini Token metrics
        gemini_q = select(
            func.coalesce(func.sum(ProviderUsageEvent.input_tokens), 0),
            func.coalesce(func.sum(ProviderUsageEvent.output_tokens), 0),
            func.coalesce(func.sum(ProviderUsageEvent.total_tokens), 0),
            func.coalesce(func.sum(ProviderUsageEvent.embedding_tokens), 0),
            func.count(),
            func.coalesce(func.bool_or(ProviderUsageEvent.is_estimated), False),
        ).where(
            ProviderUsageEvent.user_id == user.id,
            ProviderUsageEvent.provider == "gemini",
        )
        g_res = (await db.execute(gemini_q)).first()
        gemini_usage = GeminiUsageBreakdown(
            input_tokens=g_res[0],
            output_tokens=g_res[1],
            total_tokens=g_res[2],
            embedding_tokens=g_res[3],
            request_count=g_res[4],
            has_estimated_usage=bool(g_res[5]),
        )

        # 6. Tavily Search metrics
        tavily_q = select(
            func.coalesce(func.sum(ProviderUsageEvent.request_count), 0)
        ).where(
            ProviderUsageEvent.user_id == user.id,
            ProviderUsageEvent.provider == "tavily",
        )
        t_res = (await db.execute(tavily_q)).scalar() or 0
        tavily_usage = TavilyUsageBreakdown(search_count=t_res)

        return UsageSummaryResponse(
            user_id=user.id,
            email=user.email,
            tier=user.tier,
            limits=limits,
            hourly_submissions_used=hourly_used,
            daily_jobs_used=daily_used,
            daily_jobs_remaining=daily_remaining,
            monthly_jobs_used=monthly_used,
            monthly_jobs_remaining=monthly_remaining,
            concurrent_jobs_active=concurrent_active,
            gemini_usage=gemini_usage,
            tavily_usage=tavily_usage,
            daily_reset_utc=next_midnight,
            monthly_reset_utc=next_month,
        )

    @staticmethod
    async def get_user_usage_history(
        db: AsyncSession,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        provider: Optional[str] = None,
    ) -> UsageHistoryResponse:
        """Returns paginated provider usage events isolated strictly to the user."""
        filter_conds = [ProviderUsageEvent.user_id == user_id]
        if provider:
            filter_conds.append(ProviderUsageEvent.provider == provider.lower())

        total_q = select(func.count()).select_from(ProviderUsageEvent).where(*filter_conds)
        total = (await db.execute(total_q)).scalar() or 0

        offset = max(0, (page - 1) * page_size)
        items_q = (
            select(ProviderUsageEvent)
            .where(*filter_conds)
            .order_by(desc(ProviderUsageEvent.created_at))
            .offset(offset)
            .limit(page_size)
        )
        res = await db.execute(items_q)
        items = res.scalars().all()

        return UsageHistoryResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=[ProviderUsageEventResponse.model_validate(i) for i in items],
        )

    @staticmethod
    async def get_admin_usage_summary(db: AsyncSession) -> AdminUsageSummaryResponse:
        """Aggregates platform-wide usage metrics across all users."""
        total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
        total_jobs = (await db.execute(select(func.count()).select_from(ResearchJob))).scalar() or 0

        # Status breakdown
        status_q = select(ResearchJob.status, func.count()).group_by(ResearchJob.status)
        status_rows = (await db.execute(status_q)).all()
        jobs_by_status = {row[0]: row[1] for row in status_rows}

        # Token breakdown
        gemini_q = select(
            func.coalesce(func.sum(ProviderUsageEvent.total_tokens), 0),
            func.coalesce(func.sum(ProviderUsageEvent.input_tokens), 0),
            func.coalesce(func.sum(ProviderUsageEvent.output_tokens), 0),
            func.coalesce(func.sum(ProviderUsageEvent.embedding_tokens), 0),
        ).where(ProviderUsageEvent.provider == "gemini")
        g_row = (await db.execute(gemini_q)).first()

        # Tavily breakdown
        tavily_q = select(
            func.coalesce(func.sum(ProviderUsageEvent.request_count), 0)
        ).where(ProviderUsageEvent.provider == "tavily")
        t_total = (await db.execute(tavily_q)).scalar() or 0

        total_events = (await db.execute(select(func.count()).select_from(ProviderUsageEvent))).scalar() or 0

        return AdminUsageSummaryResponse(
            total_users=total_users,
            total_jobs=total_jobs,
            jobs_by_status=jobs_by_status,
            gemini_total_tokens=g_row[0],
            gemini_input_tokens=g_row[1],
            gemini_output_tokens=g_row[2],
            gemini_embedding_tokens=g_row[3],
            tavily_total_searches=t_total,
            total_events_recorded=total_events,
        )

    @staticmethod
    async def get_admin_users_usage(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 50,
    ) -> AdminUsersUsageResponse:
        """Lists per-user usage breakdown for platform administration."""
        total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0

        now = datetime.datetime.now(datetime.timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        offset = max(0, (page - 1) * page_size)
        users_q = select(User).order_by(desc(User.created_at)).offset(offset).limit(page_size)
        users = (await db.execute(users_q)).scalars().all()

        items = []
        for u in users:
            # Active jobs
            active = (
                await db.execute(
                    select(func.count())
                    .select_from(ResearchJob)
                    .where(ResearchJob.user_id == u.id, ResearchJob.status.in_(["queued", "processing"]))
                )
            ).scalar() or 0

            # Today jobs
            today = (
                await db.execute(
                    select(func.count())
                    .select_from(ResearchJob)
                    .where(ResearchJob.user_id == u.id, ResearchJob.created_at >= start_of_day)
                )
            ).scalar() or 0

            # Month jobs
            month = (
                await db.execute(
                    select(func.count())
                    .select_from(ResearchJob)
                    .where(ResearchJob.user_id == u.id, ResearchJob.created_at >= start_of_month)
                )
            ).scalar() or 0

            # Total jobs
            total_j = (
                await db.execute(
                    select(func.count())
                    .select_from(ResearchJob)
                    .where(ResearchJob.user_id == u.id)
                )
            ).scalar() or 0

            # Total tokens
            tokens = (
                await db.execute(
                    select(func.coalesce(func.sum(ProviderUsageEvent.total_tokens + ProviderUsageEvent.embedding_tokens), 0))
                    .where(ProviderUsageEvent.user_id == u.id, ProviderUsageEvent.provider == "gemini")
                )
            ).scalar() or 0

            # Total searches
            searches = (
                await db.execute(
                    select(func.coalesce(func.sum(ProviderUsageEvent.request_count), 0))
                    .where(ProviderUsageEvent.user_id == u.id, ProviderUsageEvent.provider == "tavily")
                )
            ).scalar() or 0

            items.append(
                AdminUserUsageItem(
                    user_id=u.id,
                    email=u.email,
                    name=u.name,
                    tier=u.tier,
                    role=u.role,
                    is_active=u.is_active,
                    active_jobs=active,
                    jobs_today=today,
                    jobs_this_month=month,
                    total_jobs=total_j,
                    total_tokens=tokens,
                    total_searches=searches,
                )
            )

        return AdminUsersUsageResponse(total=total_users, items=items)
