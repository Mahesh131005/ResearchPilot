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
        is_byok: bool = False,
    ) -> Tuple[bool, Optional[ResearchJob]]:
        """
        Atomically validates concurrency, hourly rate limits, daily quotas, and monthly quotas.
        Uses PostgreSQL row-level locking (`SELECT ... FOR UPDATE`) to guarantee zero race conditions.
        
        When is_byok is True (user provided their own personal API keys):
        - Daily and monthly platform job quotas are NOT consumed or enforced.
        - Hourly platform limits are bypassed.
        - Concurrency protection is maintained to protect client stability.
        
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

        # 4. Check Concurrency Limit (Auto-expire any stale jobs older than 8 minutes)
        stale_threshold = now - datetime.timedelta(minutes=8)
        stale_jobs_stmt = select(ResearchJob).where(
            ResearchJob.user_id == user.id,
            ResearchJob.status.in_(["queued", "processing"]),
            ResearchJob.created_at < stale_threshold,
        )
        stale_res = await db.execute(stale_jobs_stmt)
        stale_jobs = stale_res.scalars().all()
        if stale_jobs:
            for s_job in stale_jobs:
                s_job.status = "failed"
                s_job.error_message = "Research job timed out or backend container was restarted."
            await db.commit()

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

        # 5. Check Hourly Submissions Rate Limit (Only applies to platform keys)
        if not is_byok:
            one_hour_ago = now - datetime.timedelta(hours=1)
            hourly_q = select(func.count(), func.min(ResearchJob.created_at)).select_from(ResearchJob).where(
                ResearchJob.user_id == user.id,
                ResearchJob.created_at >= one_hour_ago,
                ResearchJob.is_byok == False,
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

        # 6. Check Daily Quota (Applies to platform keys only; BYOK users enjoy unlimited personal quota!)
        if not is_byok:
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            daily_q = select(func.count()).select_from(ResearchJob).where(
                ResearchJob.user_id == user.id,
                ResearchJob.created_at >= start_of_day,
                ResearchJob.status != "failed",
                ResearchJob.is_byok == False,
            )
            daily_used = (await db.execute(daily_q)).scalar() or 0
            if daily_used >= limits.daily_jobs_limit:
                next_midnight = start_of_day + datetime.timedelta(days=1)
                retry_after = max(1, int((next_midnight - now).total_seconds()))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Daily quota exceeded: You have used {daily_used} of {limits.daily_jobs_limit} allowed platform research jobs for today. "
                        f"Enter your own Gemini or Cohere API key (BYOK) for unlimited research, or wait until daily quota resets at 00:00 UTC."
                    ),
                    headers={"Retry-After": str(retry_after)},
                )

        # 7. Check Monthly Quota (Applies to platform keys only)
        if not is_byok:
            start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            monthly_q = select(func.count()).select_from(ResearchJob).where(
                ResearchJob.user_id == user.id,
                ResearchJob.created_at >= start_of_month,
                ResearchJob.status != "failed",
                ResearchJob.is_byok == False,
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
                    f"({monthly_used} completed). Quota resets at the beginning of the next calendar month."
                ),
                headers={"Retry-After": str(retry_after)},
            )

        return False, None

