import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from app.api.deps import get_db, get_current_active_user, require_admin
from app.core.config import settings
from app.models.research import User, ResearchJob
from app.models.billing import UserWallet, CostLedgerEntry, ProviderPricing
from app.schemas.billing import (
    UserWalletResponse,
    CostLedgerEntryResponse,
    ProviderPricingResponse,
    ProviderPricingCreate,
    ProviderPricingUpdate,
    BillingOverviewResponse,
    CreateCheckoutRequest,
    CheckoutSessionResponse,
    AdminFinancialsOverviewResponse,
    AdminUserSpendingResponse,
)
from app.services.billing_service import BillingService

router = APIRouter(prefix="/billing", tags=["billing"])

@router.get("/wallet", response_model=UserWalletResponse)
async def get_my_wallet(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves credit wallet and balance details for the current user."""
    wallet = await BillingService.get_or_create_wallet(db, current_user.id)
    avail = max(0.0, float(wallet.balance_usd) - float(wallet.reserved_usd))
    return UserWalletResponse(
        id=wallet.id,
        user_id=wallet.user_id,
        balance_usd=float(wallet.balance_usd),
        reserved_usd=float(wallet.reserved_usd),
        available_balance_usd=avail,
        lifetime_spent_usd=float(wallet.lifetime_spent_usd),
        monthly_budget_usd=float(wallet.monthly_budget_usd) if wallet.monthly_budget_usd else None,
        auto_recharge=wallet.auto_recharge,
        tier=current_user.tier,
    )


@router.get("/overview", response_model=BillingOverviewResponse)
async def get_billing_overview(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves wallet balance, recent financial transactions, active pricing matrix, and system state."""
    wallet = await BillingService.get_or_create_wallet(db, current_user.id)
    avail = max(0.0, float(wallet.balance_usd) - float(wallet.reserved_usd))
    wallet_resp = UserWalletResponse(
        id=wallet.id,
        user_id=wallet.user_id,
        balance_usd=float(wallet.balance_usd),
        reserved_usd=float(wallet.reserved_usd),
        available_balance_usd=avail,
        lifetime_spent_usd=float(wallet.lifetime_spent_usd),
        monthly_budget_usd=float(wallet.monthly_budget_usd) if wallet.monthly_budget_usd else None,
        auto_recharge=wallet.auto_recharge,
        tier=current_user.tier,
    )

    # Query recent 15 transactions
    stmt = (
        select(CostLedgerEntry)
        .where(CostLedgerEntry.user_id == current_user.id)
        .order_by(desc(CostLedgerEntry.created_at))
        .limit(15)
    )
    res = await db.execute(stmt)
    entries = res.scalars().all()
    transactions = [
        CostLedgerEntryResponse(
            id=e.id,
            job_id=e.job_id,
            entry_type=e.entry_type,
            amount_usd=float(e.amount_usd),
            balance_before_usd=float(e.balance_before_usd),
            balance_after_usd=float(e.balance_after_usd),
            reserved_before_usd=float(e.reserved_before_usd),
            reserved_after_usd=float(e.reserved_after_usd),
            idempotency_key=e.idempotency_key,
            description=e.description,
            created_at=e.created_at,
        )
        for e in entries
    ]

    # Query active pricing matrix
    p_stmt = select(ProviderPricing).where(ProviderPricing.is_active == True).order_by(ProviderPricing.provider)
    p_res = await db.execute(p_stmt)
    pricing_list = [
        ProviderPricingResponse(
            id=p.id,
            provider=p.provider,
            model_name=p.model_name,
            operation_type=p.operation_type,
            unit_type=p.unit_type,
            input_rate_usd=float(p.input_rate_usd),
            output_rate_usd=float(p.output_rate_usd),
            fixed_request_rate_usd=float(p.fixed_request_rate_usd),
            is_active=p.is_active,
            version=p.version,
            effective_from=p.effective_from,
            effective_to=p.effective_to,
            created_at=p.created_at,
        )
        for p in p_res.scalars().all()
    ]

    budget_ok, _ = await BillingService.check_global_budget_limits(db)

    return BillingOverviewResponse(
        wallet=wallet_resp,
        recent_transactions=transactions,
        pricing_matrix=pricing_list,
        global_circuit_breaker_active=not budget_ok or not settings.BILLABLE_OPERATIONS_ENABLED,
    )


@router.get("/transactions", response_model=List[CostLedgerEntryResponse])
async def get_my_transactions(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
):
    """Retrieves full itemized financial transaction history for the authenticated user."""
    stmt = (
        select(CostLedgerEntry)
        .where(CostLedgerEntry.user_id == current_user.id)
        .order_by(desc(CostLedgerEntry.created_at))
        .limit(limit)
    )
    res = await db.execute(stmt)
    return [
        CostLedgerEntryResponse(
            id=e.id,
            job_id=e.job_id,
            entry_type=e.entry_type,
            amount_usd=float(e.amount_usd),
            balance_before_usd=float(e.balance_before_usd),
            balance_after_usd=float(e.balance_after_usd),
            reserved_before_usd=float(e.reserved_before_usd),
            reserved_after_usd=float(e.reserved_after_usd),
            idempotency_key=e.idempotency_key,
            description=e.description,
            created_at=e.created_at,
        )
        for e in res.scalars().all()
    ]


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout(
    req: CreateCheckoutRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Creates a Stripe Checkout Session to top up credit balance.
    Operates in live mode if STRIPE_SECRET_KEY is configured, or simulated mock mode.
    """
    session_data = await BillingService.create_checkout_session(
        db,
        user=current_user,
        amount_usd=req.amount_usd,
        success_url=req.success_url,
        cancel_url=req.cancel_url,
    )
    return CheckoutSessionResponse(
        session_id=session_data["session_id"],
        checkout_url=session_data["checkout_url"],
        amount_usd=session_data["amount_usd"],
        mode=session_data["mode"],
        status=session_data["status"],
    )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature"),
):
    """
    Stripe payment webhook receiver.
    Validates cryptographic signature (in live mode) and idempotently credits user wallets.
    """
    payload_bytes = await request.body()
    result = await BillingService.process_stripe_webhook_event(
        db, payload_bytes=payload_bytes, sig_header=stripe_signature
    )
    return result


# ==============================================================================
# Admin Financial & Pricing Endpoints
# ==============================================================================

@router.get("/admin/financials/overview", response_model=AdminFinancialsOverviewResponse)
async def get_admin_financials_overview(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """(Admin) Platform-wide aggregate spending, global budget tracking, and wallet metrics."""
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Query spending totals
    q_day = select(func.coalesce(func.sum(CostLedgerEntry.amount_usd), 0)).where(
        CostLedgerEntry.entry_type == "job_settlement",
        CostLedgerEntry.created_at >= start_of_day,
    )
    day_spent = abs(float((await db.execute(q_day)).scalar() or 0))

    q_month = select(func.coalesce(func.sum(CostLedgerEntry.amount_usd), 0)).where(
        CostLedgerEntry.entry_type == "job_settlement",
        CostLedgerEntry.created_at >= start_of_month,
    )
    month_spent = abs(float((await db.execute(q_month)).scalar() or 0))

    q_life = select(func.coalesce(func.sum(CostLedgerEntry.amount_usd), 0)).where(
        CostLedgerEntry.entry_type == "job_settlement",
    )
    life_spent = abs(float((await db.execute(q_life)).scalar() or 0))

    # Query wallet aggregates
    q_wallets = select(
        func.count(UserWallet.id),
        func.coalesce(func.sum(UserWallet.balance_usd), 0),
        func.coalesce(func.sum(UserWallet.reserved_usd), 0),
    )
    w_row = (await db.execute(q_wallets)).first()
    wallet_count = w_row[0] or 0
    total_balances = float(w_row[1] or 0)
    total_reserved = float(w_row[2] or 0)

    budget_ok, _ = await BillingService.check_global_budget_limits(db)
    active_cb = not budget_ok or not settings.BILLABLE_OPERATIONS_ENABLED

    return AdminFinancialsOverviewResponse(
        global_daily_budget_usd=settings.GLOBAL_DAILY_BUDGET_USD,
        global_monthly_budget_usd=settings.GLOBAL_MONTHLY_BUDGET_USD,
        global_spent_today_usd=round(day_spent, 4),
        global_spent_this_month_usd=round(month_spent, 4),
        global_spent_lifetime_usd=round(life_spent, 4),
        active_circuit_breaker=active_cb,
        total_user_wallets=wallet_count,
        total_user_balances_usd=round(total_balances, 2),
        total_reserved_usd=round(total_reserved, 2),
    )


@router.get("/admin/financials/users", response_model=List[AdminUserSpendingResponse])
async def get_admin_user_spending(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
):
    """(Admin) Individual user wallet balances, lifetime spending, and activity."""
    stmt = (
        select(User, UserWallet, func.count(ResearchJob.id))
        .join(UserWallet, User.id == UserWallet.user_id, isouter=True)
        .join(ResearchJob, User.id == ResearchJob.user_id, isouter=True)
        .group_by(User.id, UserWallet.id)
        .order_by(desc(UserWallet.lifetime_spent_usd))
        .limit(limit)
    )
    res = await db.execute(stmt)
    items = []
    for user, wallet, job_count in res.all():
        bal = float(wallet.balance_usd) if wallet else 0.0
        resv = float(wallet.reserved_usd) if wallet else 0.0
        spent = float(wallet.lifetime_spent_usd) if wallet else 0.0
        items.append(
            AdminUserSpendingResponse(
                user_id=user.id,
                email=user.email,
                tier=user.tier,
                balance_usd=bal,
                reserved_usd=resv,
                lifetime_spent_usd=spent,
                total_jobs=job_count or 0,
            )
        )
    return items


@router.get("/admin/pricing", response_model=List[ProviderPricingResponse])
async def get_admin_pricing_matrix(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """(Admin) View complete provider pricing matrix including inactive/historical rates."""
    stmt = select(ProviderPricing).order_by(ProviderPricing.provider, ProviderPricing.version.desc())
    res = await db.execute(stmt)
    return [
        ProviderPricingResponse(
            id=p.id,
            provider=p.provider,
            model_name=p.model_name,
            operation_type=p.operation_type,
            unit_type=p.unit_type,
            input_rate_usd=float(p.input_rate_usd),
            output_rate_usd=float(p.output_rate_usd),
            fixed_request_rate_usd=float(p.fixed_request_rate_usd),
            is_active=p.is_active,
            version=p.version,
            effective_from=p.effective_from,
            effective_to=p.effective_to,
            created_at=p.created_at,
        )
        for p in res.scalars().all()
    ]


@router.post("/admin/pricing", response_model=ProviderPricingResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_pricing(
    data: ProviderPricingCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """(Admin) Create a new version of provider pricing, archiving prior active version."""
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)

    # Deactivate existing active rate for this provider & operation
    stmt_old = select(ProviderPricing).where(
        ProviderPricing.provider == data.provider,
        ProviderPricing.operation_type == data.operation_type,
        ProviderPricing.is_active == True,
    )
    if data.model_name:
        stmt_old = stmt_old.where(ProviderPricing.model_name == data.model_name)

    old_rates = (await db.execute(stmt_old)).scalars().all()
    next_ver = 1
    for old_r in old_rates:
        old_r.is_active = False
        old_r.effective_to = now
        next_ver = max(next_ver, old_r.version + 1)

    new_pricing = ProviderPricing(
        id=uuid.uuid4(),
        provider=data.provider,
        model_name=data.model_name,
        operation_type=data.operation_type,
        unit_type=data.unit_type,
        input_rate_usd=data.input_rate_usd,
        output_rate_usd=data.output_rate_usd,
        fixed_request_rate_usd=data.fixed_request_rate_usd,
        effective_from=now,
        is_active=data.is_active,
        version=next_ver,
    )
    db.add(new_pricing)
    await db.commit()
    await db.refresh(new_pricing)

    return ProviderPricingResponse(
        id=new_pricing.id,
        provider=new_pricing.provider,
        model_name=new_pricing.model_name,
        operation_type=new_pricing.operation_type,
        unit_type=new_pricing.unit_type,
        input_rate_usd=float(new_pricing.input_rate_usd),
        output_rate_usd=float(new_pricing.output_rate_usd),
        fixed_request_rate_usd=float(new_pricing.fixed_request_rate_usd),
        is_active=new_pricing.is_active,
        version=new_pricing.version,
        effective_from=new_pricing.effective_from,
        effective_to=new_pricing.effective_to,
        created_at=new_pricing.created_at,
    )
