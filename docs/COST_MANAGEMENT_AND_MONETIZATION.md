# ResearchPilot — Cost Management, Global Budgets & Monetization Architecture

## 1. Executive Summary & Design Principles

Commercial multi-agent AI systems coordinate multiple LLM generation steps, vector embeddings, and live external web search APIs. Without backend-enforced monetary controls, concurrent research requests can incur unpredictable API costs or exhaust provider budgets.

ResearchPilot implements a **closed-loop monetary cost accounting, atomic reservation, and monetization engine** built upon four core principles:

1. **Versioned Provider Pricing**: Provider rates are never hardcoded. Rates for Gemini tokens (input/output), embeddings, and Tavily searches reside in a versioned, configurable database schema (`ProviderPricing`).
2. **Atomic Budget Reservations**: Concurrent research jobs must never double-spend the same remaining balance. Pre-execution reservation holds ($0.05 per job) are acquired atomically using PostgreSQL row-level locks (`SELECT ... FOR UPDATE`).
3. **Idempotent Reconciliation**: Usage events and financial ledger entries enforce unique idempotency keys. Workflows calculate actual itemized costs upon completion (or failure), refunding unspent reservations back to the user's wallet.
4. **Global System Spending Ceilings**: Platform-wide daily and monthly spending caps (`GLOBAL_DAILY_BUDGET_USD`, `GLOBAL_MONTHLY_BUDGET_USD`) act as an automated circuit breaker, pausing new billable tasks before unexpected provider billing surges occur.

---

## 2. Monetary Lifecycle & The 4-Phase Reservation Protocol

```
[ Client Request ]
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ Phase 1: Pre-Execution Budget Reservation              │
│ 1. Validate System Daily & Monthly Spending Ceilings   │
│ 2. Acquire Atomic Lock: SELECT ... FOR UPDATE          │
│ 3. Check wallet balance >= $0.05 reservation hold      │
│ 4. Deduct $0.05 from balance -> Add $0.05 to reserved  │
│ 5. Record 'reservation_hold' in cost_ledger_entries    │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│ Phase 2: Asynchronous Multi-Agent Execution            │
│ • Planner Agent generates subquestions                │
│ • Web Research Agent calls Tavily                      │
│ • Document Agent queries pgvector Embeddings           │
│ • Fact Checker verifies claims                         │
│ • Report Writer synthesizes report                     │
│ -> Every call logs a ProviderUsageEvent with tokens    │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│ Phase 3: Cost Itemization & Pricing Calculation        │
│ 1. Fetch all ProviderUsageEvents for this job_id       │
│ 2. Match against active ProviderPricing version        │
│ 3. Compute cost_usd for each event                     │
│ 4. Total actual cost = Sum(event.cost_usd)             │
│ 5. Update research_jobs.cost_usd = total_actual_cost   │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│ Phase 4: Atomic Settlement & Balance Reconciliation    │
│ 1. Acquire Lock on UserWallet: SELECT ... FOR UPDATE   │
│ 2. Release reserved hold ($0.05)                       │
│ 3. If reserved > actual:                               │
│      Refund difference (reserved - actual) to balance  │
│    If actual > reserved:                               │
│      Deduct remaining overage from balance             │
│ 4. Increment lifetime_spent_usd by actual cost         │
│ 5. Record 'job_settlement' in cost_ledger_entries      │
└────────────────────────────────────────────────────────┘
```

---

## 3. Database Models & Schema Design

### 3.1 `ProviderPricing` (Versioned Rates)
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID (PK)` | Unique identifier |
| `provider` | `String(50)` | `"gemini"` or `"tavily"` |
| `model_name` | `String(100)` | Target model (e.g., `"gemini-2.5-flash"`) |
| `operation_type` | `String(50)` | `"llm_generation"`, `"embedding"`, `"web_search"` |
| `unit_type` | `String(50)` | `"per_1m_tokens"`, `"per_request"` |
| `input_rate_usd` | `Numeric(12, 6)` | Cost per unit input |
| `output_rate_usd`| `Numeric(12, 6)` | Cost per unit output |
| `fixed_request_rate_usd` | `Numeric(12, 6)` | Cost per flat API request (Tavily) |
| `is_active` | `Boolean` | True for currently applicable version |
| `version` | `Integer` | Incrementing version counter |

### 3.2 `UserWallet` (Credit Balances & In-Flight Holds)
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID (PK)` | Unique identifier |
| `user_id` | `UUID (FK)` | Bound to `users.id` (1-to-1) |
| `balance_usd` | `Numeric(12, 4)` | Available unreserved credit balance |
| `reserved_usd` | `Numeric(12, 4)` | Sum of in-flight reservation holds |
| `lifetime_spent_usd` | `Numeric(12, 4)` | Total settled expenditure |
| `monthly_budget_usd` | `Numeric(12, 4)` | Tier-defined monthly spending cap |
| `stripe_customer_id` | `String(255)` | Linked Stripe customer ID |

### 3.3 `CostLedgerEntry` (Double-Entry Audit Ledger)
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID (PK)` | Unique identifier |
| `user_id` | `UUID (FK)` | Bound to user account |
| `job_id` | `UUID (FK)` | Bound to research job (nullable) |
| `entry_type` | `String(50)` | `"credit_grant"`, `"reservation_hold"`, `"job_settlement"`, `"stripe_payment"` |
| `amount_usd` | `Numeric(12, 6)` | Signed financial amount (positive credit, negative debit) |
| `balance_before_usd` | `Numeric(12, 4)` | Balance prior to entry |
| `balance_after_usd` | `Numeric(12, 4)` | Balance immediately after entry |
| `idempotency_key` | `String(255)` | Unique constraint preventing duplicate ledger operations |
| `description` | `String(255)` | Human-readable explanation |

---

## 4. Global Spending Limits & Circuit Breaker

To prevent runaway costs on production deployments:
- **`GLOBAL_DAILY_BUDGET_USD`** (Default: `$50.00`): Maximum daily spending across all tenants combined.
- **`GLOBAL_MONTHLY_BUDGET_USD`** (Default: `$500.00`): Maximum monthly spending across all tenants.
- **Automated Circuit Breaker**: If expenditure reaches either threshold, `BillingService.reserve_job_budget` immediately rejects new billable research submissions with `HTTP 503 Service Unavailable`.
- **Emergency Kill-Switch**: `BILLABLE_OPERATIONS_ENABLED = false` immediately halts all remote API calls globally.

---

## 5. Stripe Billing Integration & Webhook Handling

### 5.1 Dual-Mode Operation (`live` vs `mock`)
- **Live Mode**: Set `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET`. The application calls `stripe.checkout.Session.create` and verifies webhook payloads with `stripe.Webhook.construct_event`.
- **Deterministic Mock Mode**: When Stripe keys are omitted (e.g. local development, continuous integration, beta testing), `BillingService` generates deterministic mock checkout sessions (`cs_test_...`) and accepts simulated webhook events, allowing 100% of the monetization flow to be tested automatically.

### 5.2 Idempotent Webhook Processing
- Webhook events (`checkout.session.completed`, `payment_intent.succeeded`) derive an idempotency key: `stripe_{session_id}`.
- Attempting to replay an identical webhook payload detects the existing `CostLedgerEntry` and returns `{"status": "already_processed"}`, preventing duplicate wallet credits.

---

## 6. Regulatory & Privacy Compliance

1. **Zero Credential Exposure**: Stripe secret keys and webhook secrets reside strictly in the backend environment.
2. **Anti-Enumeration 404s**: Unowned billing records or cross-tenant inspection attempts return `HTTP 404 Not Found`.
3. **Audit Trail**: Every monetary movement is preserved in `cost_ledger_entries` for financial auditing and reconciliation.

