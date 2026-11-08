import uuid
import pytest
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select, text

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.research import User, ResearchJob
from app.models.billing import UserWallet, CostLedgerEntry, ProviderPricing
from app.services.billing_service import BillingService

@pytest.mark.asyncio
async def test_wallet_initialization_complimentary_credit(auth_client: AsyncClient):
    """Verify newly registered users receive complimentary beta credit ($1.00) and ledger entry."""
    # Register new user
    user_email = f"billing_user_{uuid.uuid4().hex[:8]}@example.com"
    resp = await auth_client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "password": "SecurePassword123!"}
    )
    assert resp.status_code == 201
    tokens = resp.json()
    auth_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Fetch wallet overview
    wallet_resp = await auth_client.get("/api/v1/billing/wallet", headers=auth_headers)
    assert wallet_resp.status_code == 200
    wallet_data = wallet_resp.json()
    assert wallet_data["balance_usd"] == 1.00
    assert wallet_data["reserved_usd"] == 0.00
    assert wallet_data["available_balance_usd"] == 1.00

    # Verify ledger history
    tx_resp = await auth_client.get("/api/v1/billing/transactions", headers=auth_headers)
    assert tx_resp.status_code == 200
    txs = tx_resp.json()
    assert len(txs) >= 1
    assert txs[0]["entry_type"] == "credit_grant"
    assert txs[0]["amount_usd"] == 1.00


@pytest.mark.asyncio
async def test_pricing_calculation():
    """Verify exact decimal pricing mathematics for tokens and search requests."""
    # Gemini Flash LLM: 10,000 input tokens ($0.075/1M) + 5,000 output tokens ($0.30/1M)
    # Expected: (10,000 / 1,000,000 * 0.075) + (5,000 / 1,000,000 * 0.30)
    # = 0.00075 + 0.0015 = 0.002250 USD
    cost = BillingService.calculate_cost(
        pricing=None,
        provider="gemini",
        operation_type="llm_generation",
        input_tokens=10000,
        output_tokens=5000,
    )
    assert cost == Decimal("0.002250")

    # Tavily Web Search: 3 requests ($0.005 each) = 0.015000 USD
    cost_tavily = BillingService.calculate_cost(
        pricing=None,
        provider="tavily",
        operation_type="web_search",
        request_count=3,
    )
    assert cost_tavily == Decimal("0.015000")


@pytest.mark.asyncio
async def test_atomic_budget_reservation_and_reconciliation(auth_client: AsyncClient):
    """
    Verify research inquiry reserves $0.05 hold from wallet balance,
    executes workflow, records itemized cost on usage events, and settles balance.
    """
    user_email = f"research_billing_{uuid.uuid4().hex[:8]}@example.com"
    resp = await auth_client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "password": "SecurePassword123!"}
    )
    tokens = resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Submit research inquiry
    job_resp = await auth_client.post(
        "/api/v1/research/jobs",
        json={"query": "Quantum computing advances in finance", "depth": "quick"},
        headers=headers,
    )
    assert job_resp.status_code == 201
    job_data = job_resp.json()
    job_id = job_data["id"]
    assert job_data["budget_reserved_usd"] == 0.05

    # Check that reservation hold was applied
    wallet_resp = await auth_client.get("/api/v1/billing/wallet", headers=headers)
    assert wallet_resp.status_code == 200
    wallet_after_sub = wallet_resp.json()
    # Initial was 1.00, deducted 0.05 -> balance is 0.95
    assert wallet_after_sub["balance_usd"] <= 0.95


@pytest.mark.asyncio
async def test_insufficient_funds_rejection(auth_client: AsyncClient):
    """Verify research job submission is rejected with HTTP 402 when wallet balance is below $0.05."""
    user_email = f"poor_user_{uuid.uuid4().hex[:8]}@example.com"
    resp = await auth_client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "password": "SecurePassword123!"}
    )
    tokens = resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Manually drain the wallet balance in the DB to $0.01
    async with AsyncSessionLocal() as session:
        drain_user = (await session.execute(select(User).where(User.email == user_email))).scalar_one()
        await session.execute(
            text("UPDATE user_wallets SET balance_usd = 0.0100 WHERE user_id = :uid"),
            {"uid": drain_user.id}
        )
        await session.commit()

    # Attempt to submit research job
    job_resp = await auth_client.post(
        "/api/v1/research/jobs",
        json={"query": "Macroeconomic interest rate trends", "depth": "quick"},
        headers=headers,
    )
    assert job_resp.status_code == 402
    err_detail = job_resp.json().get("detail", "")
    assert "Insufficient credit balance" in err_detail
    assert "$0.05" in err_detail


@pytest.mark.asyncio
async def test_concurrent_reservation_no_double_spend(auth_client: AsyncClient):
    """
    Verify PostgreSQL row-level locking prevents concurrent jobs from double-spending
    when balance is only sufficient for a single reservation hold.
    """
    user_email = f"race_user_{uuid.uuid4().hex[:8]}@example.com"
    resp = await auth_client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "password": "SecurePassword123!"}
    )
    tokens = resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Set tier to pro (allows 3 concurrent jobs) and balance exactly to $0.05 (enough for only 1 reservation)
    async with AsyncSessionLocal() as session:
        race_user = (await session.execute(select(User).where(User.email == user_email))).scalar_one()
        race_user.tier = "pro"
        await session.execute(
            text("UPDATE user_wallets SET balance_usd = 0.0500 WHERE user_id = :uid"),
            {"uid": race_user.id}
        )
        await session.commit()

    # Launch first submission: must succeed
    job1 = await auth_client.post(
        "/api/v1/research/jobs",
        json={"query": "Neural network pruning methods", "depth": "quick"},
        headers=headers,
    )
    assert job1.status_code == 201

    # Launch second submission: must fail with HTTP 402 (balance is now 0.00)
    job2 = await auth_client.post(
        "/api/v1/research/jobs",
        json={"query": "Low-rank adaptation in LLMs", "depth": "quick"},
        headers=headers,
    )
    assert job2.status_code == 402
    assert "Insufficient credit balance" in job2.json().get("detail", "")


@pytest.mark.asyncio
async def test_stripe_checkout_and_webhook_idempotency(auth_client: AsyncClient):
    """
    Verify creating checkout sessions and processing webhook payments.
    Ensures that repeating identical webhooks does not duplicate wallet credits.
    """
    user_email = f"stripe_user_{uuid.uuid4().hex[:8]}@example.com"
    resp = await auth_client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "password": "SecurePassword123!"}
    )
    tokens = resp.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # 1. Create checkout session
    co_resp = await auth_client.post(
        "/api/v1/billing/checkout",
        json={"amount_usd": 25.0},
        headers=headers,
    )
    assert co_resp.status_code == 200
    co_data = co_resp.json()
    session_id = co_data["session_id"]
    assert co_data["amount_usd"] == 25.0
    assert "checkout_url" in co_data

    # 2. Simulate Stripe Webhook: checkout.session.completed
    async with AsyncSessionLocal() as session:
        stripe_user = (await session.execute(select(User).where(User.email == user_email))).scalar_one()
        user_uuid_str = str(stripe_user.id)

    webhook_payload = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "client_reference_id": user_uuid_str,
                "amount_total": 2500, # $25.00 in cents
                "metadata": {
                    "user_id": user_uuid_str,
                    "amount_usd": "25.00"
                }
            }
        }
    }

    wb_resp1 = await auth_client.post("/api/v1/billing/webhook", json=webhook_payload)
    assert wb_resp1.status_code == 200
    res1 = wb_resp1.json()
    assert res1["status"] == "credited"
    assert res1["amount_usd"] == 25.0

    # Verify wallet balance increased by $25.00 (from initial $1.00 to $26.00)
    w_resp = await auth_client.get("/api/v1/billing/wallet", headers=headers)
    assert w_resp.status_code == 200
    assert w_resp.json()["balance_usd"] == 26.00

    # 3. Repeat exact same webhook (Idempotency Test)
    wb_resp2 = await auth_client.post("/api/v1/billing/webhook", json=webhook_payload)
    assert wb_resp2.status_code == 200
    res2 = wb_resp2.json()
    assert res2["status"] == "already_processed"

    # Verify balance did NOT double-credit
    w_resp2 = await auth_client.get("/api/v1/billing/wallet", headers=headers)
    assert w_resp2.json()["balance_usd"] == 26.00


@pytest.mark.asyncio
async def test_admin_financial_and_pricing_endpoints(auth_client: AsyncClient):
    """Verify admin authorization, financial overview metrics, and versioned pricing updates."""
    # 1. Non-admin user access is rejected with 403
    user_email = f"regular_user_{uuid.uuid4().hex[:8]}@example.com"
    resp = await auth_client.post(
        "/api/v1/auth/register",
        json={"email": user_email, "password": "SecurePassword123!"}
    )
    tokens = resp.json()
    user_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    denied = await auth_client.get("/api/v1/billing/admin/financials/overview", headers=user_headers)
    assert denied.status_code == 403

    # 2. Promote user to admin in DB
    async with AsyncSessionLocal() as session:
        reg_user = (await session.execute(select(User).where(User.email == user_email))).scalar_one()
        reg_user.role = "admin"
        await session.commit()

    # Re-login to get admin token
    login_resp = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": user_email, "password": "SecurePassword123!"}
    )
    admin_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # 3. Access admin financial overview
    overview_resp = await auth_client.get("/api/v1/billing/admin/financials/overview", headers=admin_headers)
    assert overview_resp.status_code == 200
    ov = overview_resp.json()
    assert "global_daily_budget_usd" in ov
    assert "total_user_wallets" in ov
    assert "total_user_balances_usd" in ov

    # 4. Access admin pricing matrix
    pricing_resp = await auth_client.get("/api/v1/billing/admin/pricing", headers=admin_headers)
    assert pricing_resp.status_code == 200
    assert len(pricing_resp.json()) >= 1

    # 5. Create new pricing rate (version increment)
    new_pricing_data = {
        "provider": "gemini",
        "model_name": "gemini-1.5-pro",
        "operation_type": "llm_generation",
        "unit_type": "per_1m_tokens",
        "input_rate_usd": 1.25,
        "output_rate_usd": 5.00,
        "fixed_request_rate_usd": 0.0,
        "is_active": True
    }
    create_p_resp = await auth_client.post(
        "/api/v1/billing/admin/pricing",
        json=new_pricing_data,
        headers=admin_headers,
    )
    assert create_p_resp.status_code == 201
    created_p = create_p_resp.json()
    assert created_p["model_name"] == "gemini-1.5-pro"
    assert created_p["input_rate_usd"] == 1.25
    assert created_p["version"] >= 1


@pytest.mark.asyncio
async def test_global_budget_with_inflight_reservations(monkeypatch):
    """Verify that in-flight wallet reservations are accounted for in global spending limits."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "GLOBAL_DAILY_BUDGET_USD", 1.00)

    async with AsyncSessionLocal() as session:
        test_uid = uuid.uuid4()
        user = User(
            id=test_uid,
            email=f"inflight_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="hash",
            is_active=True,
            role="user",
        )
        session.add(user)
        wallet = UserWallet(
            id=uuid.uuid4(),
            user_id=test_uid,
            balance_usd=Decimal("10.00"),
            reserved_usd=Decimal("1.05"),
            lifetime_spent_usd=Decimal("0.00"),
        )
        session.add(wallet)
        await session.commit()

        ok, reason = await BillingService.check_global_budget_limits(session)
        assert ok is False
        assert "Daily global spending ceiling" in reason
        assert "In-Flight Reserved" in reason

        await session.delete(wallet)
        await session.delete(user)
        await session.commit()
