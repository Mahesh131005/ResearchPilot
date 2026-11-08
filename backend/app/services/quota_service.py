import uuid
import datetime
from typing import Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.research import User, ResearchJob
from app.services.usage_service import UsageService

class QuotaService:
    @staticmethod
    async def check_and_reserve_job(
        db: AsyncSession,
        user: User,
        client_token: Optional[str] = None,
    ) -> Tuple[bool, Optional[ResearchJob]]:
        """
        Atomically validates concurrency, hourly rate limits, daily quotas, and monthly quotas.
        Uses PostgreSQL row-level locking (`SELECT ... FOR UPDATE`) to guarantee zero race conditions.
        
        Returns:
            (is_retry: bool, existing_job: Optional[ResearchJob])
            If is_retry is True, an existing job matching client_token is returned without deducting quota.
        """
        # 1. Idempotency Check: if client_token matches an existing job for this user, return it directly
        if client_token:
            stmt = select(ResearchJob).where(
                ResearchJob.user_id == user.id,
                ResearchJob.client_token == client_token,
            )
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                return True, existing

        # 2. Acquire atomic row-level lock on the User record to serialize concurrent submissions
        lock_stmt = select(User.id).where(User.id == user.id).with_for_update()
        await db.execute(lock_stmt)

        # 3. Retrieve effective limits for this user's tier and custom overrides
        limits = await UsageService.get_user_limits(db, user)
        now = datetime.datetime.now(datetime.timezone.utc)

        # 4. Check Concurrency Limit
        concurrent_q = select(func.count()).select_from(ResearchJob).where(
            ResearchJob.user_id == user.id,
            ResearchJob.status.in_(["queued", "processing"]),
        )
        active_jobs = (await db.execute(concurrent_q)).scalar() or 0
        if active_jobs >= limits.concurrent_jobs_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Concurrency limit exceeded: You have {active_jobs} research job(s) currently in progress. "
                    f"Your tier allows a maximum of {limits.concurrent_jobs_limit} concurrent job(s). "
                    f"Please wait for your active job to finish before launching a new one."
                ),
                headers={"Retry-After": "30"},
            )

        # 5. Check Hourly Submissions Rate Limit
        one_hour_ago = now - datetime.timedelta(hours=1)
        hourly_q = select(func.count(), func.min(ResearchJob.created_at)).select_from(ResearchJob).where(
            ResearchJob.user_id == user.id,
            ResearchJob.created_at >= one_hour_ago,
        )
        hourly_row = (await db.execute(hourly_q)).first()
        hourly_used = hourly_row[0] or 0
        oldest_in_window = hourly_row[1]

        if hourly_used >= limits.hourly_submissions_limit:
            if oldest_in_window:
                elapsed = (now - oldest_in_window).total_seconds()
                retry_after = max(1, int(3600 - elapsed))
            else:
                retry_after = 3600
            mins = max(1, retry_after // 60)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit exceeded: You have reached your limit of {limits.hourly_submissions_limit} research submissions per hour "
                    f"({hourly_used} submitted). Please retry in {mins} minute(s)."
                ),
                headers={"Retry-After": str(retry_after)},
            )

        # 6. Check Daily Quota
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        daily_q = select(func.count()).select_from(ResearchJob).where(
            ResearchJob.user_id == user.id,
            ResearchJob.created_at >= start_of_day,
            ResearchJob.status != "failed",
        )
        daily_used = (await db.execute(daily_q)).scalar() or 0
        if daily_used >= limits.daily_jobs_limit:
            next_midnight = start_of_day + datetime.timedelta(days=1)
            retry_after = max(1, int((next_midnight - now).total_seconds()))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Daily quota exceeded: You have used {daily_used} of {limits.daily_jobs_limit} allowed research jobs for today. "
                    f"Daily quota resets at 00:00 UTC."
                ),
                headers={"Retry-After": str(retry_after)},
            )

        # 7. Check Monthly Quota
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_q = select(func.count()).select_from(ResearchJob).where(
            ResearchJob.user_id == user.id,
            ResearchJob.created_at >= start_of_month,
            ResearchJob.status != "failed",
        )
        monthly_used = (await db.execute(monthly_q)).scalar() or 0
        if monthly_used >= limits.monthly_jobs_limit:
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                next_month = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
            retry_after = max(1, int((next_month - now).total_seconds()))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Monthly quota exceeded: You have reached the monthly ceiling of {limits.monthly_jobs_limit} research jobs "
                    f"({monthly_used} completed). Quota resets at the beginning of the next calendar month."
                ),
                headers={"Retry-After": str(retry_after)},
            )

        return False, None

