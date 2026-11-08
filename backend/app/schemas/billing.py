import uuid
import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class ProviderPricingBase(BaseModel):
    provider: str
    model_name: Optional[str] = None
    operation_type: str
    unit_type: str = "per_1m_tokens"
    input_rate_usd: float = 0.0
    output_rate_usd: float = 0.0
    fixed_request_rate_usd: float = 0.0
    is_active: bool = True

class ProviderPricingCreate(ProviderPricingBase):
    pass

class ProviderPricingUpdate(BaseModel):
    input_rate_usd: Optional[float] = None
    output_rate_usd: Optional[float] = None
    fixed_request_rate_usd: Optional[float] = None
    is_active: Optional[bool] = None

class ProviderPricingResponse(ProviderPricingBase):
    id: uuid.UUID
    version: int
    effective_from: datetime.datetime
    effective_to: Optional[datetime.datetime] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class UserWalletResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    balance_usd: float
    reserved_usd: float
    available_balance_usd: float
    lifetime_spent_usd: float
    monthly_budget_usd: Optional[float] = None
    auto_recharge: bool = False
    tier: str = "free"

    model_config = ConfigDict(from_attributes=True)


class CostLedgerEntryResponse(BaseModel):
    id: uuid.UUID
    job_id: Optional[uuid.UUID] = None
    entry_type: str
    amount_usd: float
    balance_before_usd: float
    balance_after_usd: float
    reserved_before_usd: float
    reserved_after_usd: float
    idempotency_key: Optional[str] = None
    description: str
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class BillingOverviewResponse(BaseModel):
    wallet: UserWalletResponse
    recent_transactions: List[CostLedgerEntryResponse]
    pricing_matrix: List[ProviderPricingResponse]
    global_circuit_breaker_active: bool = False


class CreateCheckoutRequest(BaseModel):
    amount_usd: float = Field(..., ge=1.0, le=500.0, description="Amount to add to credit balance in USD")
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class CheckoutSessionResponse(BaseModel):
    session_id: str
    checkout_url: str
    amount_usd: float
    mode: str = "mock" # "mock" or "live"
    status: str = "open"


class AdminFinancialsOverviewResponse(BaseModel):
    global_daily_budget_usd: float
    global_monthly_budget_usd: float
    global_spent_today_usd: float
    global_spent_this_month_usd: float
    global_spent_lifetime_usd: float
    active_circuit_breaker: bool
    total_user_wallets: int
    total_user_balances_usd: float
    total_reserved_usd: float


class AdminUserSpendingResponse(BaseModel):
    user_id: uuid.UUID
    email: str
    tier: str
    balance_usd: float
    reserved_usd: float
    lifetime_spent_usd: float
    total_jobs: int

