import uuid
import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any, List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, update

from app.core.config import settings
from app.models.research import User, ResearchJob
from app.models.usage import ProviderUsageEvent
from app.models.billing import ProviderPricing, UserWallet, CostLedgerEntry

# Provisional default rates if database pricing is empty
PROVISIONAL_RATES = {
    "gemini": {
        "llm_generation": {
            "unit": "per_1m_tokens",
            "input": Decimal("0.075000"),
            "output": Decimal("0.300000"),
            "fixed": Decimal("0.000000"),
        },
        "structured_generation": {
            "unit": "per_1m_tokens",
            "input": Decimal("0.075000"),
            "output": Decimal("0.300000"),
            "fixed": Decimal("0.000000"),
        },
        "embedding": {
            "unit": "per_1m_tokens",
            "input": Decimal("0.020000"),
            "output": Decimal("0.000000"),
            "fixed": Decimal("0.000000"),
        },
    },
    "tavily": {
        "web_search": {
            "unit": "per_request",
            "input": Decimal("0.000000"),
            "output": Decimal("0.000000"),
            "fixed": Decimal("0.005000"),
        }
    }
}


class BillingService:
    @staticmethod
    async def get_or_create_wallet(db: AsyncSession, user_id: uuid.UUID) -> UserWallet:
        """Retrieves user wallet or initializes it with complimentary credit."""
        stmt = select(UserWallet).where(UserWallet.user_id == user_id)
        res = await db.execute(stmt)
        wallet = res.scalar_one_or_none()
        if wallet:
            return wallet

        starter_credit = Decimal(str(settings.FREE_TIER_COMPLIMENTARY_BALANCE_USD))
        wallet = UserWallet(
            id=uuid.uuid4(),
            user_id=user_id,
            balance_usd=starter_credit,
            reserved_usd=Decimal("0.0000"),
            lifetime_spent_usd=Decimal("0.0000"),
            monthly_budget_usd=Decimal(str(settings.PRO_TIER_MONTHLY_BUDGET_USD)),
        )
        db.add(wallet)
        await db.flush()

        ledger = CostLedgerEntry(
            id=uuid.uuid4(),
            user_id=user_id,
            entry_type="credit_grant",
            amount_usd=starter_credit,
            balance_before_usd=Decimal("0.0000"),
            balance_after_usd=starter_credit,
            reserved_before_usd=Decimal("0.0000"),
            reserved_after_usd=Decimal("0.0000"),
            description="Complimentary beta research starter credit",
            idempotency_key=f"signup_credit_{user_id}",
        )
        db.add(ledger)
        await db.flush()
        return wallet

    @staticmethod
    async def get_active_pricing(
        db: AsyncSession,
        provider: str,
        operation_type: str,
        model_name: Optional[str] = None
    ) -> Optional[ProviderPricing]:
        """Fetches active versioned pricing record from database."""
        stmt = select(ProviderPricing).where(
            ProviderPricing.provider == provider,
            ProviderPricing.operation_type == operation_type,
            ProviderPricing.is_active == True,
        )
        if model_name:
            stmt_model = stmt.where(ProviderPricing.model_name == model_name)
            res_model = await db.execute(stmt_model)
            row = res_model.scalar_one_or_none()
            if row:
                return row

        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    def calculate_cost(
        pricing: Optional[ProviderPricing],
        provider: str,
        operation_type: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        embedding_tokens: int = 0,
        request_count: int = 1,
    ) -> Decimal:
        """Computes monetary cost in USD rounded to 6 decimal places."""
        if pricing:
            input_rate = pricing.input_rate_usd
            output_rate = pricing.output_rate_usd
            fixed_rate = pricing.fixed_request_rate_usd
        else:
            p_prov = PROVISIONAL_RATES.get(provider, {}).get(operation_type, {})
            input_rate = p_prov.get("input", Decimal("0.000000"))
            output_rate = p_prov.get("output", Decimal("0.000000"))
            fixed_rate = p_prov.get("fixed", Decimal("0.000000"))

        cost = Decimal("0.000000")
        if input_tokens > 0:
            cost += (Decimal(input_tokens) / Decimal(1000000)) * input_rate
        if output_tokens > 0:
            cost += (Decimal(output_tokens) / Decimal(1000000)) * output_rate
        if embedding_tokens > 0:
            cost += (Decimal(embedding_tokens) / Decimal(1000000)) * input_rate
        if request_count > 0 and fixed_rate > 0:
            cost += Decimal(request_count) * fixed_rate

        return cost.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    @staticmethod
    async def check_global_budget_limits(db: AsyncSession) -> Tuple[bool, str]:
        """
        Validates current system expenditure against daily and monthly global caps,
        accounting for both settled ledger transactions and active in-flight reservations.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Query today's settled expenditure
        q_day = select(func.coalesce(func.sum(CostLedgerEntry.amount_usd), 0)).where(
            CostLedgerEntry.entry_type == "job_settlement",
            CostLedgerEntry.created_at >= start_of_day,
        )
        day_spent = abs(Decimal(str((await db.execute(q_day)).scalar() or 0)))

        # Query month's settled expenditure
        q_month = select(func.coalesce(func.sum(CostLedgerEntry.amount_usd), 0)).where(
            CostLedgerEntry.entry_type == "job_settlement",
            CostLedgerEntry.created_at >= start_of_month,
        )
        month_spent = abs(Decimal(str((await db.execute(q_month)).scalar() or 0)))

        # Query active in-flight reservations across all user wallets
        q_inflight = select(func.coalesce(func.sum(UserWallet.reserved_usd), 0))
        total_in_flight = abs(Decimal(str((await db.execute(q_inflight)).scalar() or 0)))

        committed_day = day_spent + total_in_flight
        committed_month = month_spent + total_in_flight

        max_daily = Decimal(str(settings.GLOBAL_DAILY_BUDGET_USD))
        max_monthly = Decimal(str(settings.GLOBAL_MONTHLY_BUDGET_USD))

        if committed_day >= max_daily:
            return False, f"Daily global spending ceiling of ${max_daily:.2f} reached (Spent: ${day_spent:.4f}, In-Flight Reserved: ${total_in_flight:.4f})."
        if committed_month >= max_monthly:
            return False, f"Monthly global spending ceiling of ${max_monthly:.2f} reached (Spent: ${month_spent:.4f}, In-Flight Reserved: ${total_in_flight:.4f})."

        return True, ""

    @staticmethod
    async def reserve_job_budget(
        db: AsyncSession,
        user: User,
        client_token: Optional[str] = None
    ) -> Decimal:
        """
        Atomically reserves an estimated budget hold ($0.05) from the user's wallet.
        Uses PostgreSQL row-level locking (`SELECT ... FOR UPDATE`) to prevent race conditions.
        """
        # 1. Global budget ceiling circuit breaker check
        budget_ok, reason = await BillingService.check_global_budget_limits(db)
        if not budget_ok:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Automated budget limit reached: {reason} New research submissions are paused.",
            )

        reservation_amount = Decimal(str(settings.DEFAULT_JOB_RESERVATION_USD))

        # 2. Acquire atomic row-level lock on the User's wallet
        wallet_stmt = select(UserWallet).where(UserWallet.user_id == user.id).with_for_update()
        res = await db.execute(wallet_stmt)
        wallet = res.scalar_one_or_none()

        if not wallet:
            wallet = await BillingService.get_or_create_wallet(db, user.id)
            # Re-lock after creation
            wallet_stmt = select(UserWallet).where(UserWallet.user_id == user.id).with_for_update()
            res = await db.execute(wallet_stmt)
            wallet = res.scalar_one()

        # 3. Check sufficient available balance
        if wallet.balance_usd < reservation_amount:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=(
                    f"Insufficient credit balance: A research inquiry requires a ${reservation_amount:.2f} estimated reservation hold. "
                    f"Your available balance is ${wallet.balance_usd:.2f}. "
                    f"Please top up your balance to continue."
                ),
            )

        # 4. Atomic deduction and reservation hold
        bal_before = wallet.balance_usd
        res_before = wallet.reserved_usd

        wallet.balance_usd = (wallet.balance_usd - reservation_amount).quantize(Decimal("0.0001"))
        wallet.reserved_usd = (wallet.reserved_usd + reservation_amount).quantize(Decimal("0.0001"))

        ledger_entry = CostLedgerEntry(
            id=uuid.uuid4(),
            user_id=user.id,
            entry_type="reservation_hold",
            amount_usd=-reservation_amount,
            balance_before_usd=bal_before,
            balance_after_usd=wallet.balance_usd,
            reserved_before_usd=res_before,
            reserved_after_usd=wallet.reserved_usd,
            description=f"Estimated pre-execution budget hold (${reservation_amount:.2f})",
            idempotency_key=f"hold_{client_token}" if client_token else None,
        )
        db.add(ledger_entry)
        await db.flush()

        return reservation_amount

    @staticmethod
    async def reconcile_job_cost(
        db: AsyncSession,
        job_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Decimal:
        """
        Reconciles in-flight reservation against actual provider usage events for a job.
        Computes exact itemized cost, updates events, updates job, and settles wallet balance.
        """
        # 1. Lock wallet row atomically
        wallet_stmt = select(UserWallet).where(UserWallet.user_id == user_id).with_for_update()
        res_wallet = await db.execute(wallet_stmt)
        wallet = res_wallet.scalar_one_or_none()
        if not wallet:
            wallet = await BillingService.get_or_create_wallet(db, user_id)
            wallet_stmt = select(UserWallet).where(UserWallet.user_id == user_id).with_for_update()
            res_wallet = await db.execute(wallet_stmt)
            wallet = res_wallet.scalar_one()

        # 2. Fetch Job and reserved amount
        job = await db.get(ResearchJob, job_id)
        reserved_amount = (
            job.budget_reserved_usd
            if job and job.budget_reserved_usd is not None
            else Decimal("0.000000")
        )

        # 3. Query all ProviderUsageEvents associated with this job
        events_stmt = select(ProviderUsageEvent).where(ProviderUsageEvent.job_id == job_id)
        events_res = await db.execute(events_stmt)
        events = events_res.scalars().all()

        total_actual_cost = Decimal("0.000000")
        for ev in events:
            pricing = await BillingService.get_active_pricing(
                db, ev.provider, ev.operation_type, ev.model_name
            )
            ev_cost = BillingService.calculate_cost(
                pricing=pricing,
                provider=ev.provider,
                operation_type=ev.operation_type,
                input_tokens=ev.input_tokens,
                output_tokens=ev.output_tokens,
                embedding_tokens=ev.embedding_tokens,
                request_count=ev.request_count,
            )
            ev.cost_usd = ev_cost
            if pricing:
                ev.pricing_id = pricing.id
            total_actual_cost += ev_cost

        # 4. Update ResearchJob cost
        if job:
            job.cost_usd = total_actual_cost

        # 5. Reconcile with UserWallet
        bal_before = wallet.balance_usd
        res_before = wallet.reserved_usd

        # Release the reservation hold
        wallet.reserved_usd = max(
            Decimal("0.0000"),
            (wallet.reserved_usd - reserved_amount).quantize(Decimal("0.0001"))
        )

        if reserved_amount >= total_actual_cost:
            # Over-reserved: refund the difference
            refund = (reserved_amount - total_actual_cost).quantize(Decimal("0.0001"))
            wallet.balance_usd = (wallet.balance_usd + refund).quantize(Decimal("0.0001"))
            wallet.lifetime_spent_usd = (wallet.lifetime_spent_usd + total_actual_cost).quantize(Decimal("0.0001"))

            desc = f"Job settlement (Reserved: ${reserved_amount:.4f}, Actual: ${total_actual_cost:.4f}, Refund: ${refund:.4f})"
        else:
            # Under-reserved: deduct remaining overage
            overage = (total_actual_cost - reserved_amount).quantize(Decimal("0.0001"))
            wallet.balance_usd = max(Decimal("0.0000"), (wallet.balance_usd - overage).quantize(Decimal("0.0001")))
            wallet.lifetime_spent_usd = (wallet.lifetime_spent_usd + total_actual_cost).quantize(Decimal("0.0001"))

            desc = f"Job settlement with overage (Reserved: ${reserved_amount:.4f}, Actual: ${total_actual_cost:.4f}, Overage: ${overage:.4f})"

        # 6. Record Settlement in Cost Ledger
        ledger = CostLedgerEntry(
            id=uuid.uuid4(),
            user_id=user_id,
            job_id=job_id,
            entry_type="job_settlement",
            amount_usd=-total_actual_cost,
            balance_before_usd=bal_before,
            balance_after_usd=wallet.balance_usd,
            reserved_before_usd=res_before,
            reserved_after_usd=wallet.reserved_usd,
            description=desc,
            idempotency_key=f"settle_{job_id}",
            meta_info={
                "reserved_usd": float(reserved_amount),
                "actual_cost_usd": float(total_actual_cost),
                "event_count": len(events),
            }
        )
        db.add(ledger)
        await db.commit()

        return total_actual_cost

    @staticmethod
    async def create_checkout_session(
        db: AsyncSession,
        user: User,
        amount_usd: float,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates a Stripe Checkout Session or returns a deterministic mock session."""
        amt_decimal = Decimal(str(amount_usd)).quantize(Decimal("0.01"))
        wallet = await BillingService.get_or_create_wallet(db, user.id)

        default_success = success_url or "http://localhost:5173/billing?payment=success"
        default_cancel = cancel_url or "http://localhost:5173/billing?payment=cancelled"

        if settings.effective_stripe_mode == "live" and settings.STRIPE_SECRET_KEY:
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"ResearchPilot AI Credits (${amt_decimal:.2f})",
                            "description": "Prepaid AI computation and research credits.",
                        },
                        "unit_amount": int(amt_decimal * 100),
                    },
                    "quantity": 1,
                }],
                mode="payment",
                client_reference_id=str(user.id),
                metadata={
                    "user_id": str(user.id),
                    "amount_usd": str(amt_decimal),
                },
                success_url=f"{default_success}&session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=default_cancel,
            )
            return {
                "session_id": session.id,
                "checkout_url": session.url,
                "amount_usd": float(amt_decimal),
                "mode": "live",
                "status": "open",
            }

        # Deterministic offline mock checkout
        mock_session_id = f"cs_test_{uuid.uuid4().hex[:16]}"
        mock_checkout_url = f"{default_success}&session_id={mock_session_id}"
        return {
            "session_id": mock_session_id,
            "checkout_url": mock_checkout_url,
            "amount_usd": float(amt_decimal),
            "mode": "mock",
            "status": "open",
        }

    @staticmethod
    async def process_stripe_webhook_event(
        db: AsyncSession,
        payload_bytes: bytes,
        sig_header: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Processes Stripe webhook events and credits user wallet idempotently."""
        import json
        event = None

        if settings.effective_stripe_mode == "live" and settings.STRIPE_WEBHOOK_SECRET:
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY
            try:
                event = stripe.Webhook.construct_event(
                    payload_bytes, sig_header, settings.STRIPE_WEBHOOK_SECRET
                )
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid webhook signature: {str(e)}")
        else:
            try:
                event = json.loads(payload_bytes.decode("utf-8"))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {str(e)}")

        event_type = event.get("type", "")
        data_obj = event.get("data", {}).get("object", {})

        if event_type in ["checkout.session.completed", "payment_intent.succeeded"]:
            session_id = data_obj.get("id") or str(uuid.uuid4())
            metadata = data_obj.get("metadata", {})
            user_id_str = metadata.get("user_id") or data_obj.get("client_reference_id")
            amount_usd_str = metadata.get("amount_usd")

            if not amount_usd_str and "amount_total" in data_obj:
                amount_usd_str = str(Decimal(data_obj["amount_total"]) / Decimal(100))

            if user_id_str and amount_usd_str:
                user_id = uuid.UUID(user_id_str)
                credit_amount = Decimal(amount_usd_str).quantize(Decimal("0.01"))

                # Lock wallet and enforce idempotency
                wallet_stmt = select(UserWallet).where(UserWallet.user_id == user_id).with_for_update()
                wallet_res = await db.execute(wallet_stmt)
                wallet = wallet_res.scalar_one_or_none()
                if not wallet:
                    wallet = await BillingService.get_or_create_wallet(db, user_id)

                # Check if this session was already credited
                idempotency_key = f"stripe_{session_id}"
                check_stmt = select(CostLedgerEntry).where(CostLedgerEntry.idempotency_key == idempotency_key)
                existing_entry = (await db.execute(check_stmt)).scalar_one_or_none()
                if existing_entry:
                    return {"status": "already_processed", "idempotency_key": idempotency_key}

                bal_before = wallet.balance_usd
                res_before = wallet.reserved_usd

                wallet.balance_usd = (wallet.balance_usd + credit_amount).quantize(Decimal("0.0001"))

                ledger = CostLedgerEntry(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    entry_type="stripe_payment",
                    amount_usd=credit_amount,
                    balance_before_usd=bal_before,
                    balance_after_usd=wallet.balance_usd,
                    reserved_before_usd=res_before,
                    reserved_after_usd=res_before,
                    description=f"Stripe payment credit (${credit_amount:.2f})",
                    idempotency_key=idempotency_key,
                    meta_info={"session_id": session_id, "mode": settings.effective_stripe_mode},
                )
                db.add(ledger)
                await db.commit()
                return {"status": "credited", "amount_usd": float(credit_amount), "user_id": str(user_id)}

        return {"status": "ignored", "event_type": event_type}

