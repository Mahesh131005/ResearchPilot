import pytest
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, update

from app.main import app
from app.db.session import AsyncSessionLocal
from app.models.research import User, ResearchJob
from app.models.usage import UserQuota
from app.core.security import hash_password, create_access_token

@pytest.fixture
async def rate_limit_user():
    """Creates a dedicated test user for rate limit and quota testing."""
    async with AsyncSessionLocal() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"ratelimit_{uuid.uuid4().hex[:8]}@example.com",
            name="Rate Limit Tester",
            hashed_password=hash_password("ComplexP@ssw0rd!2026"),
            role="user",
            tier="free",
            is_active=True,
            must_change_password=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

@pytest.fixture
def rate_limit_client(rate_limit_user):
    """Authenticated client for the rate limit test user."""
    token = create_access_token({"sub": str(rate_limit_user.id), "email": rate_limit_user.email, "role": rate_limit_user.role})
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token}"}), rate_limit_user

@pytest.mark.asyncio
async def test_concurrent_job_limit(rate_limit_client):
    client, user = rate_limit_client

    # 1. Launch first research job
    res1 = await client.post(
        "/api/v1/research/jobs",
        json={"query": "Analysis of credit risk models in retail banking", "depth": "quick", "enable_web": False, "enable_documents": False},
    )
    assert res1.status_code == 201
    job1_id = res1.json()["id"]

    # 2. Immediately attempt second job while job 1 is in progress/queued
    res2 = await client.post(
        "/api/v1/research/jobs",
        json={"query": "Analysis of liquidity coverage ratio in banking", "depth": "quick", "enable_web": False, "enable_documents": False},
    )
    assert res2.status_code == 429
    assert "Retry-After" in res2.headers
    assert "Concurrency limit exceeded" in res2.json()["detail"]

    # Clean up job1 to completed so other tests can run
    async with AsyncSessionLocal() as session:
        job1 = await session.get(ResearchJob, uuid.UUID(job1_id))
        if job1:
            job1.status = "completed"
            await session.commit()

@pytest.mark.asyncio
async def test_simultaneous_concurrent_requests_race_condition(rate_limit_client):
    client, user = rate_limit_client

    # Ensure no active jobs first
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(ResearchJob)
            .where(ResearchJob.user_id == user.id, ResearchJob.status.in_(["queued", "processing"]))
            .values(status="completed")
        )
        await session.commit()

    # Fire two requests at the exact same millisecond
    req1 = client.post(
        "/api/v1/research/jobs",
        json={"query": "Simultaneous request Alpha on macroeconomics", "depth": "quick", "enable_web": False, "enable_documents": False},
    )
    req2 = client.post(
        "/api/v1/research/jobs",
        json={"query": "Simultaneous request Beta on macroeconomics", "depth": "quick", "enable_web": False, "enable_documents": False},
    )

    results = await asyncio.gather(req1, req2)
    status_codes = sorted([r.status_code for r in results])

    # Exactly one must succeed (201) and the other must be rejected (429)
    assert status_codes == [201, 429]
    rejected = [r for r in results if r.status_code == 429][0]
    assert "Concurrency limit exceeded" in rejected.json()["detail"]

@pytest.mark.asyncio
async def test_hourly_rate_limit(rate_limit_client):
    client, user = rate_limit_client

    # Set up 5 jobs in the database created within the last 15 minutes with status 'completed'
    async with AsyncSessionLocal() as session:
        # Clear existing active jobs
        await session.execute(
            update(ResearchJob).where(ResearchJob.user_id == user.id).values(status="completed")
        )
        now = datetime.now(timezone.utc)
        for i in range(5):
            past_job = ResearchJob(
                id=uuid.uuid4(),
                user_id=user.id,
                query=f"Past research query {i}",
                depth="quick",
                status="completed",
                created_at=now - timedelta(minutes=10 + i),
            )
            session.add(past_job)
        await session.commit()

    # Attempt 6th submission within the hour
    res = await client.post(
        "/api/v1/research/jobs",
        json={"query": "Sixth hourly submission query on asset pricing", "depth": "quick", "enable_web": False, "enable_documents": False},
    )
    assert res.status_code == 429
    assert "Retry-After" in res.headers
    assert "Rate limit exceeded" in res.json()["detail"]
    assert "research submissions per hour" in res.json()["detail"]

@pytest.mark.asyncio
async def test_daily_quota_limit(rate_limit_client):
    client, user = rate_limit_client

    # Configure user with custom daily limit of 3 for testing
    async with AsyncSessionLocal() as session:
        quota = UserQuota(
            id=uuid.uuid4(),
            user_id=user.id,
            daily_jobs_limit=3,
            hourly_submissions_limit=20, # loosen hourly limit so daily limit is hit first
        )
        session.add(quota)

        # Seed 3 completed jobs today
        now = datetime.now(timezone.utc)
        for i in range(3):
            j = ResearchJob(
                id=uuid.uuid4(),
                user_id=user.id,
                query=f"Daily seeded job {i}",
                depth="quick",
                status="completed",
                created_at=now - timedelta(hours=2 + i),
            )
            session.add(j)
        await session.commit()

    # Attempt 4th submission today
    res = await client.post(
        "/api/v1/research/jobs",
        json={"query": "Fourth daily query attempting to exceed daily quota", "depth": "quick", "enable_web": False, "enable_documents": False},
    )
    assert res.status_code == 429
    assert "Daily quota exceeded" in res.json()["detail"]
    assert "3 of 3" in res.json()["detail"]

@pytest.mark.asyncio
async def test_monthly_quota_limit(rate_limit_client):
    client, user = rate_limit_client

    # Configure user with monthly limit of 2
    async with AsyncSessionLocal() as session:
        quota = await session.execute(select(UserQuota).where(UserQuota.user_id == user.id))
        q = quota.scalar_one_or_none()
        if not q:
            q = UserQuota(id=uuid.uuid4(), user_id=user.id)
            session.add(q)
        q.monthly_jobs_limit = 2
        q.daily_jobs_limit = 10
        q.hourly_submissions_limit = 10
        await session.commit()

        # Seed 2 jobs this month
        now = datetime.now(timezone.utc)
        for i in range(2):
            j = ResearchJob(
                id=uuid.uuid4(),
                user_id=user.id,
                query=f"Monthly seeded job {i}",
                depth="quick",
                status="completed",
                created_at=now - timedelta(days=1 + i),
            )
            session.add(j)
        await session.commit()

    res = await client.post(
        "/api/v1/research/jobs",
        json={"query": "Third job exceeding monthly quota", "depth": "quick", "enable_web": False, "enable_documents": False},
    )
    assert res.status_code == 429
    assert "Monthly quota exceeded" in res.json()["detail"]

@pytest.mark.asyncio
async def test_idempotent_retry_prevents_double_counting(rate_limit_client):
    client, user = rate_limit_client

    token_key = f"client-idempotent-{uuid.uuid4().hex}"

    # First submission with client_token
    res1 = await client.post(
        "/api/v1/research/jobs",
        json={
            "query": "Unique idempotency test query for network protocols",
            "depth": "quick",
            "enable_web": False,
            "enable_documents": False,
            "client_token": token_key,
        },
    )
    assert res1.status_code == 201
    job_id = res1.json()["id"]

    # Retry submission with exact same client_token
    res2 = await client.post(
        "/api/v1/research/jobs",
        json={
            "query": "Unique idempotency test query for network protocols",
            "depth": "quick",
            "enable_web": False,
            "enable_documents": False,
            "client_token": token_key,
        },
    )
    # Must return the existing job without failing concurrency or double-counting
    assert res2.status_code == 201
    assert res2.json()["id"] == job_id
    assert res2.json()["client_token"] == token_key

@pytest.mark.asyncio
async def test_emergency_kill_switch_blocks_live_billable_operations(rate_limit_client):
    client, user = rate_limit_client
    from app.core.config import settings

    orig_billable = settings.BILLABLE_OPERATIONS_ENABLED
    orig_provider_mode = settings.PROVIDER_MODE
    orig_gemini_key = settings.GEMINI_API_KEY
    try:
        # Simulate live provider mode with emergency kill-switch disabled
        settings.BILLABLE_OPERATIONS_ENABLED = False
        settings.PROVIDER_MODE = "live"
        settings.GEMINI_API_KEY = "dummy-live-key"

        res = await client.post(
            "/api/v1/research/jobs",
            json={
                "query": "Billable operation query that must be blocked",
                "depth": "quick",
                "enable_web": False,
                "enable_documents": False,
            },
        )
        assert res.status_code == 503
        assert "BILLABLE_OPERATIONS_ENABLED=False" in res.json()["detail"]

        # Verify documents, usage, and past reports remain accessible
        usage_res = await client.get("/api/v1/usage/me")
        assert usage_res.status_code == 200

        doc_res = await client.get("/api/v1/documents")
        assert doc_res.status_code == 200

    finally:
        settings.BILLABLE_OPERATIONS_ENABLED = orig_billable
        settings.PROVIDER_MODE = orig_provider_mode
        settings.GEMINI_API_KEY = orig_gemini_key
