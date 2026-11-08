# ResearchPilot — Release Checklist & Deployment Guide

This document defines the operational procedures for running ResearchPilot locally during development and the mandatory prerequisites for rolling out to a production environment.

---

## 1. Quick Local Execution

### Option A: Complete Containerized Stack (Recommended for Demo / Testing)

The repository provides a unified `docker-compose.yml` orchestrating PostgreSQL 16 (with `pgvector`), Redis, the FastAPI backend, and the React frontend.

```bash
# 1. Clone repository and copy environment defaults
cp backend/.env.example backend/.env

# 2. Launch complete stack
docker-compose up --build -d

# 3. Verify container health
docker-compose ps
```

- **Web Frontend**: `http://localhost:5173`
- **Backend API Docs**: `http://localhost:8000/docs`
- **Liveness Probe**: `http://localhost:8000/api/v1/health`
- **Readiness Probe**: `http://localhost:8000/api/v1/health/ready`
- **System Metrics**: `http://localhost:8000/api/v1/system/metrics`

---

### Option B: Local Developer Mode (Windows + WSL PostgreSQL)

When actively developing or running test suites locally:

#### Step 1: Database Setup
Ensure PostgreSQL 16 with `pgvector` extension is running (e.g. in WSL on port 5433 or local port 5432):
```bash
# In WSL
sudo service postgresql start
# Verify pgvector extension
psql -U postgres -p 5433 -d researchpilot -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### Step 2: Backend Setup
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# Run database migrations to head
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### Step 3: Frontend Setup
```powershell
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

#### Step 4: VS Code Extension Setup
```powershell
cd vscode-extension
npm install
# In VS Code, press F5 to launch the Extension Development Host window
```

---

## 2. Public Production Release Prerequisites

Before deploying ResearchPilot to a public cloud or enterprise production cluster, complete the following prerequisites:

### A. Secrets & Cryptographic Keys
- [ ] **`SECRET_KEY`**: Replace the development secret key in `.env` with a cryptographically secure 256-bit entropy string (`openssl rand -hex 32`).
- [ ] **Initial Admin Credentials**: Set `FIRST_SUPERUSER_EMAIL` and `FIRST_SUPERUSER_PASSWORD` in production environment variables. Never commit credentials to source control.
- [ ] **Provider API Keys**: Configure `GEMINI_API_KEY` and `TAVILY_API_KEY` as encrypted secrets in your secret manager (e.g., AWS Secrets Manager, GCP Secret Manager, Vault).
- [ ] **Stripe Secret & Webhook Keys**: Replace `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` with live production keys (`sk_live_...` and `whsec_...`).

### B. Network & Infrastructure
- [ ] **TLS / HTTPS Termination**: Enforce TLS 1.3 across all incoming client traffic via a reverse proxy (Nginx, Traefik, Cloudflare, or AWS ALB).
- [ ] **Strict CORS Configuration**: Update `allow_origins` in `backend/app/main.py` to match exact production domain origins (remove `localhost` and `127.0.0.1`).
- [ ] **Reverse Proxy Request Size Limit**: Ensure Nginx / Traefik `client_max_body_size` matches the backend's `MAX_REQUEST_BODY_SIZE_MB` (30MB).
- [ ] **Redis Deployment**: Deploy a high-availability Redis instance or AWS ElastiCache / Redis Enterprise cluster for distributed caching and rate limit coordination across multiple backend replicas.

### C. Database & Persistence
- [ ] **Database Backup Schedule**: Configure automated point-in-time recovery (PITR) and daily snapshot policies on PostgreSQL.
- [ ] **Alembic Migration Verification**: Run `alembic current` and verify migrations are at head (`e3f940182b1c`) prior to switching traffic.
- [ ] **Connection Pooling**: Configure PgBouncer or connection pool sizing in `settings.DATABASE_URL` appropriate for your worker replica count.

### D. Billing & Spending Safeguards
- [ ] **Global Daily Spending Cap**: Set `GLOBAL_DAILY_BUDGET_USD` to a conservative threshold (e.g. $50.00) during launch.
- [ ] **Global Monthly Spending Cap**: Set `GLOBAL_MONTHLY_BUDGET_USD` (e.g. $500.00).
- [ ] **Emergency Kill-Switch Verification**: Confirm that `BILLABLE_OPERATIONS_ENABLED` can be toggled via environment variable or management API to immediately pause live billable calls with HTTP 503 if anomalies occur.
- [ ] **Stripe Live Webhook Endpoint**: Register `https://api.yourdomain.com/api/v1/billing/webhook` in the Stripe Dashboard with `checkout.session.completed` event subscription.

### E. Telemetry & Observability
- [ ] **Prometheus Scraping**: Configure Prometheus to scrape `/api/v1/system/metrics?format=prometheus` at 15-second intervals.
- [ ] **Alerting Thresholds**:
  - Alert if `researchpilot_memory_rss_megabytes > 1500MB`
  - Alert if daily spend exceeds 80% of `GLOBAL_DAILY_BUDGET_USD`
  - Alert if HTTP 5xx error rate exceeds 1% of total requests
- [ ] **Log Ingestion**: Direct container standard output logs to Datadog, CloudWatch, or Grafana Loki.

---

## 3. Pre-Release Verification Sign-Off

| Verification Item | Verification Command | Required Result | Verified Status |
| :--- | :--- | :--- | :---: |
| Backend Tests | `pytest -v backend/tests` | 72 passed, 0 failed | **PASSED** |
| Frontend Tests | `npm --prefix frontend test -- --run` | 12 passed, 0 failed | **PASSED** |
| Extension Tests | `npm --prefix vscode-extension test` | 25 passed, 0 failed | **PASSED** |
| Frontend Build | `npm --prefix frontend run build` | Clean build in dist/ | **PASSED** |
| Alembic Migration | `alembic -c backend/alembic.ini current` | Head: e3f940182b1c | **VERIFIED** |
| Liveness Probe | `curl http://localhost:8000/api/v1/health` | `{"status": "healthy"}` | **VERIFIED** |
| Readiness Probe | `curl http://localhost:8000/api/v1/health/ready` | `{"status": "ready"}` | **VERIFIED** |
| Security Headers | Check response headers | OWASP headers attached | **VERIFIED** |
| CSP in Webviews | Check webview HTML output | Strict CSP meta tag | **VERIFIED** |

