import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, func

from app.main import app
from app.db.session import AsyncSessionLocal
from app.models.research import User, ResearchJob
from app.models.usage import ProviderUsageEvent
from app.core.security import hash_password, create_access_token
from app.services.usage_service import UsageService
from app.agents.web_research import WebResearchAgent
from app.core.usage_context import set_usage_context, clear_usage_context

@pytest.fixture
async def regular_user():
    async with AsyncSessionLocal() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"usage_regular_{uuid.uuid4().hex[:8]}@example.com",
            name="Regular Usage Tester",
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
async def admin_user():
    async with AsyncSessionLocal() as session:
        admin = User(
            id=uuid.uuid4(),
            email=f"usage_admin_{uuid.uuid4().hex[:8]}@example.com",
            name="Admin Usage Tester",
            hashed_password=hash_password("AdminComplexP@ssw0rd!2026"),
            role="admin",
            tier="admin",
            is_active=True,
            must_change_password=False,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        return admin

@pytest.fixture
def regular_client(regular_user):
    token = create_access_token({"sub": str(regular_user.id), "email": regular_user.email, "role": regular_user.role})
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token}"}), regular_user

@pytest.fixture
def admin_client(admin_user):
    token = create_access_token({"sub": str(admin_user.id), "email": admin_user.email, "role": admin_user.role})
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token}"}), admin_user

@pytest.mark.asyncio
async def test_usage_summary_and_limits_endpoints(regular_client):
    client, user = regular_client

    # 1. Test GET /api/v1/usage/limits
    limits_res = await client.get("/api/v1/usage/limits")
    assert limits_res.status_code == 200
    limits_data = limits_res.json()
    assert limits_data["tier"] == "free"
    assert limits_data["hourly_submissions_limit"] == 5
    assert limits_data["daily_jobs_limit"] == 5
    assert limits_data["monthly_jobs_limit"] == 100
    assert limits_data["concurrent_jobs_limit"] == 1
    assert limits_data["tavily_searches_per_job_limit"] == 5

    # 2. Test GET /api/v1/usage/me
    summary_res = await client.get("/api/v1/usage/me")
    assert summary_res.status_code == 200
    summary_data = summary_res.json()
    assert summary_data["email"] == user.email
    assert summary_data["tier"] == "free"
    assert "daily_jobs_remaining" in summary_data
    assert "monthly_jobs_remaining" in summary_data
    assert "gemini_usage" in summary_data
    assert "tavily_usage" in summary_data
    assert "daily_reset_utc" in summary_data

@pytest.mark.asyncio
async def test_admin_usage_endpoints_authorization(regular_client, admin_client):
    reg_client, _ = regular_client
    adm_client, _ = admin_client

    # Regular user attempting admin endpoints -> 403 Forbidden
    res_reg_summary = await reg_client.get("/api/v1/admin/usage")
    assert res_reg_summary.status_code == 403

    res_reg_users = await reg_client.get("/api/v1/admin/usage/users")
    assert res_reg_users.status_code == 403

    # Admin user accessing admin endpoints -> 200 OK
    res_adm_summary = await adm_client.get("/api/v1/admin/usage")
    assert res_adm_summary.status_code == 200
    adm_summary_data = res_adm_summary.json()
    assert "total_users" in adm_summary_data
    assert "total_jobs" in adm_summary_data
    assert "gemini_total_tokens" in adm_summary_data
    assert "tavily_total_searches" in adm_summary_data

    res_adm_users = await adm_client.get("/api/v1/admin/usage/users")
    assert res_adm_users.status_code == 200
    adm_users_data = res_adm_users.json()
    assert "total" in adm_users_data
    assert len(adm_users_data["items"]) > 0

@pytest.mark.asyncio
async def test_cross_user_usage_isolation(regular_client):
    client_a, user_a = regular_client

    # Create another user B with a private usage event
    async with AsyncSessionLocal() as session:
        user_b = User(
            id=uuid.uuid4(),
            email=f"user_b_{uuid.uuid4().hex[:8]}@example.com",
            name="User B",
            hashed_password=hash_password("Pass123!Safe"),
            role="user",
            tier="free",
        )
        session.add(user_b)
        await session.commit()
        await session.refresh(user_b)

        # Record private event for User B
        await UsageService.record_usage_event(
            db=session,
            user_id=user_b.id,
            provider="gemini",
            operation_type="llm_generation",
            input_tokens=9999,
            output_tokens=8888,
            total_tokens=18887,
            idempotency_key=f"user-b-private-{uuid.uuid4().hex}",
        )

    # User A requests their own usage history
    res = await client_a.get("/api/v1/usage/history")
    assert res.status_code == 200
    history_data = res.json()
    
    # User A must NOT see User B's 18887 tokens
    for item in history_data["items"]:
        assert item["total_tokens"] != 18887

@pytest.mark.asyncio
async def test_idempotent_usage_recording():
    idem_key = f"idempotent-test-{uuid.uuid4().hex}"
    user_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        # Create user
        u = User(
            id=user_id,
            email=f"idem_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("Pass123!Safe"),
            role="user",
        )
        session.add(u)
        await session.commit()

        # 1. First record call
        ev1 = await UsageService.record_usage_event(
            db=session,
            user_id=user_id,
            provider="gemini",
            operation_type="structured_generation",
            input_tokens=150,
            output_tokens=300,
            total_tokens=450,
            idempotency_key=idem_key,
        )

        # 2. Duplicate record call with exact same idempotency_key
        ev2 = await UsageService.record_usage_event(
            db=session,
            user_id=user_id,
            provider="gemini",
            operation_type="structured_generation",
            input_tokens=150,
            output_tokens=300,
            total_tokens=450,
            idempotency_key=idem_key,
        )

        # Must return the identical event ID and not insert a duplicate row
        assert ev1.id == ev2.id

        # Verify only 1 row exists with this idempotency_key
        count = (
            await session.execute(
                select(func.count())
                .select_from(ProviderUsageEvent)
                .where(ProviderUsageEvent.idempotency_key == idem_key)
            )
        ).scalar()
        assert count == 1

@pytest.mark.asyncio
async def test_tavily_search_usage_and_per_job_ceiling():
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        u = User(
            id=user_id,
            email=f"tavily_test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("Pass123!Safe"),
            role="user",
        )
        session.add(u)
        job = ResearchJob(
            id=job_id,
            user_id=user_id,
            query="Tavily ceiling test",
            depth="quick",
            status="processing",
        )
        session.add(job)
        await session.commit()

    tok = set_usage_context(user_id=user_id, job_id=job_id)
    try:
        agent = WebResearchAgent()
        # Supply 8 sub-questions targeting web
        sub_questions = [
            {"id": f"sq-{i}", "question": f"Sub question query topic {i}", "source_type": "web"}
            for i in range(8)
        ]
        # Enforce max_searches = 5
        results = await agent.research(sub_questions, max_searches=5)
        assert len(results) > 0

        # Verify that exactly 5 usage events were recorded for this job
        async with AsyncSessionLocal() as session:
            count = (
                await session.execute(
                    select(func.count())
                    .select_from(ProviderUsageEvent)
                    .where(
                        ProviderUsageEvent.user_id == user_id,
                        ProviderUsageEvent.job_id == job_id,
                        ProviderUsageEvent.provider == "tavily",
                    )
                )
            ).scalar()
            assert count == 5
    finally:
        clear_usage_context(tok)
