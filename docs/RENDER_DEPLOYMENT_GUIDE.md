# ResearchPilot — Render Deployment & Production Readiness Guide

## 1. Executive Summary

This document details the production deployment architecture, configuration inventory, migration strategy, security posture, and operational constraints for deploying **ResearchPilot** to [Render](https://render.com).

The ResearchPilot platform consists of:
1. **FastAPI Web Service**: High-performance asynchronous API serving REST endpoints, Server-Sent Events (SSE) streaming, and background multi-agent LangGraph workflow execution.
2. **Managed PostgreSQL 16 with `pgvector`**: ACID-compliant relational storage, semantic vector retrieval (768-dimensional embeddings), atomic row-level quota locking, and financial cost ledger.
3. **React Single Page Application (SPA)**: Modern dashboard served as a global static site via Render CDN.
4. **VS Code Extension (`researchpilot-vscode`)**: Institutional research assistant communicating strictly via user-authenticated REST/SSE endpoints.

---

## 2. Repository Audit & Production Services Analysis

### Service Matrix

| Service | Technology | Production Requirement | Justification |
| :--- | :--- | :--- | :--- |
| **API Web Service** | FastAPI + Uvicorn (Python 3.13) | **Mandatory** | Core application gateway, authentication, RAG ingestion, and workflow orchestration. |
| **Relational Database** | Managed PostgreSQL 16 + `pgvector` | **Mandatory** | User records, document metadata, chunk embeddings (`vector(768)`), research jobs, reports, quota counters, and immutable billing ledgers. |
| **Distributed Cache / Queue (Redis)** | Redis 7 Alpine | **Not Required in Production** | Rate limiting, job concurrency, and wallet reservations are enforced natively via PostgreSQL row-level locking (`SELECT ... FOR UPDATE`). No Redis dependencies exist in `backend/requirements.txt`. Eliminating Redis saves **$7/month**. |
| **Separate Background Worker** | Celery / RQ / Arq | **Not Required in Production** | Workflows execute in-process via `asyncio.create_task`. No separate worker container is required. |
| **Web Frontend** | React 18 + Vite | **Optional / Recommended** | Can be deployed as a **Render Static Site (100% Free)** or accessed via local dev server / VS Code extension. |

### Redis Audit Finding
While `docker-compose.yml` includes a local Redis service for local caching development experiments, the production backend does **not** import or require Redis. All concurrency limits, daily/monthly quotas, and financial reservation holds are executed directly in PostgreSQL using ACID transactions and row-level serialization (`QuotaService.check_and_reserve_job` and `BillingService.reserve_job_budget`). Deploying Redis to Render is therefore unnecessary.

### Worker Architecture & Render Execution Model
ResearchPilot executes its 5-agent LangGraph workflows in-process using Python's native `asyncio.create_task(self._execute_workflow(...))`.
- When an authenticated user submits a research job (`POST /api/v1/research/jobs`), the endpoint performs atomic quota and budget reservations, creates a database record with `status="queued"`, spawns `_execute_workflow` as an asyncio background task, and **immediately returns HTTP 200** with the job UUID within ~50ms.
- Render has a strict **100-second HTTP request timeout** for client requests. Because ResearchPilot decouples job creation from workflow completion, requests never time out on job creation.
- Real-time milestone progress is observed via Server-Sent Events (`GET /api/v1/research/jobs/{id}/stream`). To prevent Render's reverse proxy from dropping idle connections during multi-agent LLM deliberations, the event generator transmits periodic heartbeat comments (`: keepalive\n\n`) every 15 seconds.

> [!WARNING]
> **Render Free Plan vs Starter Plan Constraint:**
> - On Render's **Free Web Service** tier, services automatically spin down to zero after 15 minutes of HTTP inactivity. If a service spins down or restarts during an active research task, in-memory `asyncio.create_task` tasks will be terminated abruptly.
> - For reliable, uninterrupted research jobs, the **Starter Web Service plan ($7/mo)** is strongly recommended. The Starter plan never sleeps and guarantees continuous background execution.

---

## 3. Environment Variable Inventory & Classification

Every environment variable used by ResearchPilot is categorized below as either a **Configuration** (non-sensitive, environment-specific) or a **Secret** (sensitive credential, API key, or private signing token).

### Secrets (Sensitive Credentials)

| Environment Variable | Classification | Required | Description & Security Guidelines |
| :--- | :--- | :--- | :--- |
| `SECRET_KEY` | **Secret** | **Yes** | Cryptographic secret key used for signing HS256 JWT access and refresh tokens. Must be a secure random hex or base64 string of at least 32 characters. Generated automatically in `render.yaml`. |
| `DATABASE_URL` | **Secret** | **Yes** | PostgreSQL connection URL containing database username, password, host, port, and database name. Render automatically populates this from the linked database service. |
| `INITIAL_ADMIN_PASSWORD` | **Secret** | **Yes** | Initial password for the administrator account seeded during initial database migration. The account is created with `must_change_password=True`. |
| `GEMINI_API_KEY` | **Secret** | Conditional | Google AI Studio API key. Required if `PROVIDER_MODE` is `"live"` or `"auto"` for real LLM reasoning and 768-dim embeddings. Optional if running in `"mock"` mode. |
| `TAVILY_API_KEY` | **Secret** | Conditional | Tavily Search API key. Required for live external web research agent. Optional if running in `"mock"` mode. |
| `STRIPE_SECRET_KEY` | **Secret** | Optional | Stripe API secret key (`sk_test_...` or `sk_live_...`). Required only if real Stripe payments are enabled. ResearchPilot defaults to deterministic mock payments. |
| `STRIPE_WEBHOOK_SECRET` | **Secret** | Optional | Stripe webhook signature verification secret (`whsec_...`). |

### Configuration (Non-Sensitive)

| Environment Variable | Classification | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `APP_NAME` | Configuration | `ResearchPilot` | Application name displayed in API metadata and OpenAPI docs. |
| `APP_ENV` | Configuration | `production` | Environment tier (`development`, `staging`, `production`). |
| `DEBUG` | Configuration | `False` | Disables debug mode and verbose stack traces in production. |
| `PORT` | Configuration | `10000` | Injected automatically by Render. Application listens on `0.0.0.0:${PORT:-8000}`. |
| `API_V1_STR` | Configuration | `/api/v1` | Base API routing prefix. |
| `CORS_ORIGINS` | Configuration | `*` | Comma-separated list of allowed origins or `*`. In production, set to your frontend domain (e.g., `https://researchpilot-web.onrender.com`). |
| `PROVIDER_MODE` | Configuration | `auto` | `auto` (uses live keys if configured; otherwise mocks), `mock` (forces deterministic simulation), or `live` (strictly requires API keys). |
| `BILLABLE_OPERATIONS_ENABLED` | Configuration | `true` | Emergency operational kill-switch. When `false`, blocks live LLM and web search requests while keeping reports, documents, and mock mode accessible. |
| `INITIAL_ADMIN_EMAIL` | Configuration | `admin@researchpilot.local` | Email address for initial administrator account bootstrap. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Configuration | `30` | JWT access token lifetime in minutes. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Configuration | `7` | Refresh token lifetime in days. |
| `UPLOAD_DIR` | Configuration | `/app/uploads` | Path to document upload storage on disk. Mounted to Render Persistent Disk. |
| `MAX_FILE_SIZE_MB` | Configuration | `25` | Maximum allowed individual document file upload size (PDF). |
| `MAX_REQUEST_BODY_SIZE_MB` | Configuration | `30` | Maximum allowed HTTP request payload size enforced by middleware (HTTP 413). |
| `GLOBAL_DAILY_BUDGET_USD` | Configuration | `50.0` | Global platform-wide 24-hour spending ceiling. |
| `GLOBAL_MONTHLY_BUDGET_USD` | Configuration | `500.0` | Global platform-wide monthly spending ceiling. |
| `DEFAULT_JOB_RESERVATION_USD`| Configuration | `0.05` | Provisional monetary reservation held per research job. |
| `FREE_TIER_COMPLIMENTARY_BALANCE_USD` | Configuration | `1.00` | Complimentary starting credit granted to all new users. |
| `STRIPE_MODE` | Configuration | `mock` | `mock` simulates checkout sessions; `live` connects to Stripe API. |

---

## 4. Port and Host Binding Verification

Render assigns an arbitrary port to every web service through the `$PORT` environment variable (typically `10000`).

To comply with Render networking:
1. **Entrypoint Script (`backend/docker-entrypoint.sh`)**:
   ```sh
   exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
   ```
2. **Backward Compatibility**:
   When running locally via Docker Compose or manual script where `$PORT` is unset, the parameter defaults to `8000`, preserving full compatibility with `docker-compose.yml`.
3. **Container Listening Host**:
   Uvicorn listens on `0.0.0.0` (all IPv4 interfaces), allowing Render's edge load balancer and container health probes to reach the service.

---

## 5. Database Connection Handling & Normalization

Render provides database connection strings in the standard PostgreSQL format:
`postgres://user:password@dpg-[id]-a.oregon-postgres.render.com:5432/researchpilot`

### URL Normalization Strategy
The SQLAlchemy async engine requires the `postgresql+asyncpg://` dialect prefix, while synchronous tooling (Alembic and wait scripts) requires `postgresql+psycopg2://` or `postgresql://`. Furthermore, `asyncpg` does not accept the `sslmode=require` query parameter and expects `ssl=require`.

To handle Render database URLs automatically without manual configuration:
1. **`Settings.normalize_settings` in `backend/app/core/config.py`**:
   - Detects `postgres://` or `postgresql://` and maps it to `postgresql+asyncpg://`.
   - Translates `sslmode=require` to `ssl=require` for asyncpg compatibility.
   - Automatically derives `SYNC_DATABASE_URL` (`postgresql+psycopg2://...`) for Alembic if not explicitly set.
2. **`backend/docker-entrypoint.sh` Pre-flight Check**:
   - Connects using standard `psycopg2` to verify database reachability.
   - Executes `CREATE EXTENSION IF NOT EXISTS vector;` idempotently.
   - Runs `alembic upgrade head` to apply all pending schema revisions.

---

## 6. Document Storage & Persistence Architecture

Documents uploaded by users (`.pdf` files) are stored on disk in the directory specified by `UPLOAD_DIR` (`/app/uploads`).

### Storage Options on Render:
1. **Render Persistent Disk (Recommended — Starter Tier)**:
   - Mount path: `/app/uploads`
   - Size: 5 GB (expandable dynamically in Render Dashboard)
   - Cost: $0.25/GB/month ($1.25/month for 5GB).
   - Benefit: Uploaded PDFs and generated research reports persist across container rebuilds, code updates, and service restarts.
2. **Ephemeral Disk (Free Tier Evaluation)**:
   - If deployed on the Free tier without a persistent disk, uploads reside in the container filesystem.
   - When the container restarts or a new deploy occurs, uploaded files in `/app/uploads` will be wiped, although database metadata and vector embeddings in PostgreSQL remain intact.

---

## 7. Security, CORS & Admin Bootstrap Review

### 1. Cross-Origin Resource Sharing (CORS)
- Render environments typically host the frontend on a separate subdomain (e.g., `https://researchpilot-web.onrender.com`) from the API backend (e.g., `https://researchpilot-api.onrender.com`).
- CORS origins are dynamically configured via `CORS_ORIGINS`. In `render.yaml`, `CORS_ORIGINS` is configured with wildcard `*` or specific origins.
- Security headers enforced on all responses via custom middleware:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: accelerometer=(), camera=(), microphone=(), geolocation=()`

### 2. Admin Account Bootstrap
- Alembic migration `c1f82e5a40b9_multiuser_security.py` checks for the designated admin user on initial startup.
- If the account does not exist, it automatically creates the user with:
  - Email: `settings.INITIAL_ADMIN_EMAIL`
  - Password: Hashed with bcrypt (12 salt rounds) from `settings.INITIAL_ADMIN_PASSWORD`
  - Role: `admin`
  - Tier: `enterprise` (10 concurrent jobs, 1,000 hourly submissions)
  - `must_change_password`: `True` (forces password change upon initial login).

### 3. VS Code Extension Credential Audit
- A complete security audit of `vscode-extension/` confirmed **zero hardcoded API keys, database credentials, or secrets**.
- The extension authenticates solely via the user's email and password against the configured backend URL, storing JWT tokens securely using VS Code's native `SecretStorage` API.

---

## 8. Deployment Methods

### Method A: Automated Deployment via Render Blueprint (`render.yaml`)

1. **Commit and Push**:
   Ensure `render.yaml` is committed and pushed to your GitHub or GitLab repository.
2. **Open Render Dashboard**:
   Navigate to [dashboard.render.com](https://dashboard.render.com) and click **New +** > **Blueprint**.
3. **Connect Repository**:
   Select your `ResearchPilot` repository and click **Connect**.
4. **Configure Secrets**:
   Render will inspect `render.yaml` and prompt for non-synced secrets:
   - `INITIAL_ADMIN_PASSWORD`: Enter a secure administrator password (minimum 10 characters with uppercase, digit, and symbol).
   - `GEMINI_API_KEY`: (Optional) Paste Google AI Studio API key, or leave blank to run in mock mode.
   - `TAVILY_API_KEY`: (Optional) Paste Tavily API key, or leave blank to run in mock mode.
5. **Apply Blueprint**:
   Click **Apply**. Render will:
   - Provision PostgreSQL 16 with pgvector.
   - Build the backend Docker container.
   - Attach the 5GB persistent disk at `/app/uploads`.
   - Run Alembic migrations and seed initial data.
   - Build and publish the React frontend static site.

---

### Method B: Manual Dashboard Deployment

If deploying manually without the Blueprint:

#### Step 1: Create Managed PostgreSQL
1. Click **New +** > **PostgreSQL**.
2. **Name**: `researchpilot-db`
3. **Database**: `researchpilot`
4. **User**: `researchpilot`
5. **Version**: `16`
6. **Plan**: `Starter` ($7/mo) or `Free`.
7. Once created, copy the **Internal Database URL**.

#### Step 2: Create Backend Web Service
1. Click **New +** > **Web Service**.
2. Select your repository.
3. **Environment**: `Docker`.
4. **Docker Command Context**: `backend`.
5. **Dockerfile Path**: `backend/Dockerfile`.
6. **Plan**: `Starter` ($7/mo).
7. Under **Disks**, add a disk:
   - **Name**: `researchpilot-uploads`
   - **Mount Path**: `/app/uploads`
   - **Size**: 5 GB
8. Under **Health Check Path**: `/api/v1/health`.
9. Under **Environment Variables**, add:
   - `DATABASE_URL`: Paste the Internal Database URL from Step 1.
   - `SECRET_KEY`: Generate a random 32-character string.
   - `INITIAL_ADMIN_EMAIL`: `admin@researchpilot.local`
   - `INITIAL_ADMIN_PASSWORD`: Your secure admin password.
   - `PROVIDER_MODE`: `auto`
   - `GEMINI_API_KEY`: Your Gemini API key.
   - `TAVILY_API_KEY`: Your Tavily API key.
   - `CORS_ORIGINS`: `*`
   - `UPLOAD_DIR`: `/app/uploads`
10. Click **Create Web Service**.

#### Step 3: Create Frontend Static Site
1. Click **New +** > **Static Site**.
2. Select your repository.
3. **Root Directory**: `frontend`.
4. **Build Command**: `npm ci && npm run build`.
5. **Publish Directory**: `dist`.
6. Under **Environment Variables**:
   - `VITE_API_URL`: Your backend URL (e.g. `https://researchpilot-api.onrender.com`).
7. Under **Redirects/Rewrites**:
   - **Type**: `Rewrite`
   - **Source**: `/*`
   - **Destination**: `/index.html`
8. Click **Create Static Site**.

---

## 9. Expected Operational Costs

| Component | Plan / Tier | Estimated Cost | Notes |
| :--- | :--- | :--- | :--- |
| **PostgreSQL Database** | Render Starter (1GB RAM, 10GB Disk) | $7.00 / month | Free plan database expires after 30 days. Starter plan is required for production data retention. |
| **Backend Web Service** | Render Starter (512MB RAM, 0.5 CPU) | $7.00 / month | Free tier spins down after 15m. Starter tier keeps `asyncio.create_task` research jobs running 24/7. |
| **Persistent Disk** | Render Disk (5GB @ $0.25/GB) | $1.25 / month | Retains uploaded PDF documents across deployments. |
| **Frontend Web App** | Render Static Site | **$0.00 (Free)** | Unlimited bandwidth within Render free limits, global CDN, automated SSL. |
| **Redis** | *Omitted* | **$0.00 (Free)** | Not required; handled via PostgreSQL row locks. |
| **Total Estimated Cost** | **Production Tier** | **~$15.25 / month** | |

*(For zero-cost evaluation testing, users can select the Free database and Free web service without a persistent disk; active research jobs must complete within 15 minutes before container sleep).*

---

## 10. Known Limitations & Operational Recommendations

1. **In-Process Job Execution**:
   - Multi-agent research tasks execute in the web service process. If the service is redeployed while a job is running, that specific job will fail. Clients will see a status of `failed` upon reconnection.
   - For high-volume enterprise traffic (>100 concurrent jobs), decouple job execution using Celery or ARQ with a dedicated worker pool as documented in `docs/SCALING_STRATEGY.md`.
2. **PDF Upload Storage**:
   - Without a persistent disk, uploaded PDFs reside in the container filesystem. Attaching the 5GB persistent disk at `/app/uploads` solves this.
   - For multi-instance horizontal scaling, replace local disk storage with AWS S3 or Google Cloud Storage using pre-signed URLs.
3. **Database Connection Limits**:
   - Render Starter PostgreSQL allows up to 97 concurrent connections. ResearchPilot uses SQLAlchemy `NullPool` for async sessions to avoid lingering idle connections.
4. **LLM Provider Availability & Demands**:
   - Upstream Gemini models may intermittently return `503 UNAVAILABLE` during global demand spikes. The ResearchPilot backend includes 3-stage exponential backoff retry logic (waiting 2s, 4s) in `backend/app/providers/gemini_provider.py` to transparently absorb transient upstream spikes.

