# ResearchPilot — Render Free Tier Deployment & Operational Guide

## 1. Executive Summary & Purpose

This document provides a comprehensive operational breakdown for deploying **ResearchPilot** on [Render's Free Tier](https://render.com).

This deployment tier is designed exclusively for:
- **Zero-cost personal evaluation and prototyping**
- **Demonstrations and client previews**
- **Deterministic mock-mode test runs**

> [!CAUTION]
> **NOT FOR PRODUCTION USE:**
> Render Free services are subject to automatic 15-minute spin-downs, 50–90s cold-start delays, container ephemeral storage wipes, and a hard 30-day database lifetime. This configuration must **not** be used for mission-critical institutional research or multi-tenant production SLAs.

---

## 2. Infrastructure Topology & Blueprint Components

The [`render.yaml`](file:///f:/Research%20Agent/render.yaml) Blueprint provisions exactly three components:

```
                                  ┌─────────────────────────────┐
                                  │   Render Edge / Global CDN  │
                                  └──────────────┬──────────────┘
                                                 │
                        ┌────────────────────────┴────────────────────────┐
                        │                                                 │
             ┌──────────▼──────────┐                           ┌──────────▼──────────┐
             │ researchpilot-web   │                           │ researchpilot-api   │
             │ Type: web           │                           │ Type: web           │
             │ Runtime: static     │                           │ Runtime: docker     │
             │ Plan: free ($0)     │                           │ Plan: free ($0)     │
             │ Path: frontend/dist │                           │ Port: $PORT (10000) │
             └──────────┬──────────┘                           └──────────┬──────────┘
                        │                                                 │
                        │ VITE_API_URL: https://<api-host>/api/v1         │
                        └─────────────────────────────────────────────────┤
                                                                          │
                                                               ┌──────────▼──────────┐
                                                               │ researchpilot-db    │
                                                               │ PostgreSQL 16       │
                                                               │ Extension: pgvector │
                                                               │ Plan: free ($0)     │
                                                               └─────────────────────┘
```

1. **`researchpilot-db`**: Exactly one PostgreSQL 16 database on the `free` plan. Pre-seeded with `pgvector` extension.
2. **`researchpilot-api`**: Exactly one FastAPI web service on the `free` plan. Built from `backend/Dockerfile`.
3. **`researchpilot-web`**: Exactly one frontend web service with `runtime: static` on the `free` plan. Publishes `frontend/dist`.

---

## 3. `BILLABLE_OPERATIONS_ENABLED` & Safety Architecture

To prevent accidental external API spend on Google AI Studio or Tavily during evaluation, `render.yaml` sets:
```yaml
- key: BILLABLE_OPERATIONS_ENABLED
  value: "false"
```

### A. Endpoints & Operations Blocked When `BILLABLE_OPERATIONS_ENABLED=False`
When set to `false`, the backend enforces a hard operational circuit breaker across all endpoints that would trigger billable external provider requests:

| Endpoint | Operation | Behavior when `BILLABLE_OPERATIONS_ENABLED=false` (Live Mode) | Behavior in Mock Mode (`PROVIDER_MODE=mock`) |
| :--- | :--- | :--- | :--- |
| `POST /api/v1/research/jobs` | Multi-agent research pipeline | **Blocked with HTTP 503 Service Unavailable** | **Allowed** (runs simulated 5-agent pipeline; $0.00 cost) |
| `POST /api/v1/documents/upload` | Document PDF chunking & embedding | **Blocked with HTTP 503 Service Unavailable** | **Allowed** (runs mock embedding generator; $0.00 cost) |
| `POST /api/v1/qa/query` | Grounded document Q&A synthesis | **Blocked with HTTP 503 Service Unavailable** | **Allowed** (runs mock LLM synthesis; $0.00 cost) |
| `POST /api/v1/qa/search` | Query embedding & vector search | **Blocked with HTTP 503 Service Unavailable** | **Allowed** (runs mock query embedder; $0.00 cost) |
| Agent Web Search | Tavily API search calls | **Blocked with HTTP 503 Service Unavailable** | **Allowed** (returns simulated web results; $0.00 cost) |
| `GET /api/v1/research/jobs` | View job status & history | **Allowed** (reads from PostgreSQL; zero AI cost) | **Allowed** |
| `GET /api/v1/research/jobs/{id}/report` | Retrieve completed report | **Allowed** (reads from PostgreSQL; zero AI cost) | **Allowed** |
| `GET /api/v1/research/jobs/{id}/pdf` | Export institutional PDF | **Allowed** (in-memory ReportLab generation; zero AI cost) | **Allowed** |
| `GET /api/v1/health` & `/ready` | Telemetry & Health probes | **Allowed** (reports circuit breaker status) | **Allowed** |

### B. Mock Testing vs. Real Provider Testing

```
                                  [ Incoming Request ]
                                           │
                                ┌──────────┴──────────┐
                                │ PROVIDER_MODE == ?  │
                                └──────────┬──────────┘
                        ┌──────────────────┴──────────────────┐
                        │                                     │
                   "mock" / "auto" (no keys)             "live" / "auto" (with keys)
                        │                                     │
               [ Deterministic Mock ]             ┌───────────┴───────────┐
               - 100% Offline Simulation          │ BILLABLE_OPERATIONS?  │
               - Instant response                 └───────────┬───────────┘
               - Realistic citations & claims                 │
               - ZERO external API costs             ┌────────┴────────┐
               - ALWAYS ALLOWED                      │                 │
                                                   True              False
                                                     │                 │
                                             [ Live API Call ]   [ HTTP 503 ]
                                             - Gemini 2.5 Flash  Circuit Breaker Active
                                             - Tavily Search     "Live operations paused"
```

1. **Mock Testing (Default for Free Tier):**
   - Leave `GEMINI_API_KEY` and `TAVILY_API_KEY` blank.
   - Set `PROVIDER_MODE=mock` (or `auto` without keys).
   - The entire platform functions end-to-end: multi-agent planning, simulated web search, mock fact-checking, and report synthesis run deterministically without spending a cent.
2. **Real Provider Testing:**
   - Supply valid `GEMINI_API_KEY` and `TAVILY_API_KEY` in the Render Dashboard.
   - When ready to incur provider usage, change `BILLABLE_OPERATIONS_ENABLED` to `"true"` in the Render Dashboard.
   - The platform will immediately begin routing to live Gemini 2.5 Flash and Tavily Search APIs.

---

## 4. Server-Sent Events (SSE) & Free-Tier Instance Sleeping

> [!WARNING]
> **Crucial Reality on Render Free Sleeping:**
> - Render spins down free web services after **15 minutes of zero incoming HTTP requests**, based strictly on edge routing metrics.
> - **Outgoing SSE heartbeat comments (`: keepalive\n\n`) DO NOT prevent Render from sleeping or restarting free instances.**
> - While heartbeat comments prevent 504 Gateway Timeouts from intermediate HTTP proxies, Render's edge load balancer tracks request origination. If no new HTTP requests arrive for 15 minutes, or during platform maintenance/container cycling, Render **will terminate the container regardless of open SSE connections**.

### Impact on In-Process Research Workflows
- Multi-agent research tasks execute in-process via `asyncio.create_task`.
- If the free instance spins down, cycles, or restarts while a research task is underway:
  - The in-memory task is **immediately killed**.
  - The job record in PostgreSQL will remain in status `processing` or `queued`.
  - Upon reconnection, clients can safely mark or delete the stalled job.
- **Rule of Thumb for Free Tier:** Only run `depth="quick"` or `depth="standard"` research jobs that complete within 2–4 minutes. Do not expect long-running deep research tasks to survive unattended overnight on the free tier.

---

## 5. Render Free PostgreSQL 30-Day Expiration & Backup Protocol

### A. Expiration Timeline & Grace Period
- **Day 0 to 30:** Free database operates normally (1GB storage limit).
- **Day 30:** Render **expires and suspends** the database. The API backend will fail to connect (HTTP 503).
- **Day 30 to 44 (14-Day Grace Period):** The database cannot be queried by applications, but remains available in the Render Dashboard to **upgrade to a paid Starter plan ($7/mo)** or to **export your data**.
- **Day 44:** Render **permanently deletes** the database and all underlying volumes. Data cannot be recovered.

> [!IMPORTANT]
> **No Managed Backups:**
> Render Free PostgreSQL does **NOT** provide automated daily backups, point-in-time recovery, or restore snapshots. All backups must be performed manually via `pg_dump`.

### B. Tested `pg_dump` and Restore Procedure

#### Step 1: Export Database Dump (Run before Day 30)
1. Open the Render Dashboard and navigate to `researchpilot-db`.
2. Under **Connections**, copy the **External Database URL**.
3. Run `pg_dump` from your local machine:
   ```bash
   pg_dump --clean --if-exists --no-owner --no-privileges -d "<EXTERNAL_DATABASE_URL>" -f researchpilot_backup.sql
   ```
   *Example:*
   ```bash
   pg_dump --clean --if-exists --no-owner --no-privileges -d "postgres://researchpilot:SECRET@dpg-abc-a.oregon-postgres.render.com/researchpilot" -f researchpilot_backup.sql
   ```

#### Step 2: Restore to a New Database
1. Provision a new Free PostgreSQL database in Render (`researchpilot-db-v2`).
2. Copy the new **External Database URL**.
3. Restore the backup:
   ```bash
   psql -d "<NEW_EXTERNAL_DATABASE_URL>" -f researchpilot_backup.sql
   ```
4. In `researchpilot-api` settings, update `DATABASE_URL` to point to the new database.

---

## 6. Storage Strategy: What Happens When Files Disappear

Render Free web services do not support persistent disks. All uploads reside in `/app/uploads` on the container's temporary filesystem.

### Lifecycle of Uploaded Documents
```
  [ User Uploads PDF ]
           │
           ├──► 1. PyMuPDF parses text & page numbers
           ├──► 2. Chunker splits text into 800-char blocks
           ├──► 3. Embedder generates 768-dim vectors
           └──► 4. ALL chunks, vectors, & metadata saved to PostgreSQL
```

### Container Restart Behavior:
- When Render redeploys or restarts the free container, all physical `.pdf` files in `/app/uploads` are **wiped**.
- **Semantic Retrieval is UNAFFECTED:** Document Q&A (`/api/v1/qa/query`), vector similarity search (`/api/v1/qa/search`), and multi-agent RAG research continue to work seamlessly because all text chunks and vector embeddings are stored in PostgreSQL.
- **Raw File Download Protection:** If a user requests the physical PDF binary via `GET /api/v1/documents/{document_id}/file` after a restart, the server returns an explicit **HTTP 410 Gone** error:
  ```json
  {
    "detail": "Original raw PDF binary is no longer present on ephemeral storage following a container restart. However, all parsed chunks, text, and vector embeddings remain intact in the database and are fully available for research and Q&A."
  }
  ```
  This eliminates unexplained failures or crashes.

---

## 7. Networking & Frontend Integration Verification

### A. `VITE_API_URL` Resolution
In `render.yaml`, the frontend static site injects:
```yaml
envVars:
  - key: VITE_API_URL
    fromService:
      type: web
      name: researchpilot-api
      property: host
```
- Render injects the backend hostname (e.g. `researchpilot-api.onrender.com`).
- [`frontend/src/services/api.js`](file:///f:/Research%20Agent/frontend/src/services/api.js) automatically normalizes this value:
  - If it lacks a scheme, it prepends `https://`.
  - Appends `/api/v1` to form the base URL `https://researchpilot-api.onrender.com/api/v1`.
  - If unconfigured, falls back to local proxy `/api/v1`.

### B. CORS Configuration
In `render.yaml`, `CORS_ORIGINS` is configured to `*` for the free tier. In production, this can be locked down to your static site URL (e.g. `https://researchpilot-web.onrender.com`).

---

## 8. Step-by-Step Blueprint Deployment

1. **Commit and Push:**
   ```bash
   git add render.yaml docs/RENDER_FREE_DEPLOYMENT_GUIDE.md
   git commit -m "feat(deploy): configure free-tier Render deployment"
   git push origin main
   ```
2. **Deploy on Render:**
   - Go to [dashboard.render.com](https://dashboard.render.com) > **New +** > **Blueprint**.
   - Connect your `ResearchPilot` repository.
   - Enter `INITIAL_ADMIN_PASSWORD` (min. 10 chars, uppercase, digit, symbol).
   - Leave `GEMINI_API_KEY` and `TAVILY_API_KEY` blank for mock testing.
   - Click **Apply Blueprint**.
3. **Verify Startup:**
   - Wait ~3 minutes for PostgreSQL creation, Docker build, and static asset generation.
   - Check API health: `https://<YOUR-API-HOST>/api/v1/health`
   - Log in to the web app: `admin@researchpilot.local` with your chosen password.

---

## 9. PostgreSQL Connection Architecture & Troubleshooting

### A. How Render Injects Managed Database Credentials
Render provisions managed PostgreSQL databases with an internal hostname reachable only within the Render private network:
- Internal Hostname: `dpg-xxxxxx-a` (e.g. `dpg-dbo48h3m8hqs73fgujrg-a`)
- Internal Port: `5432`
- Render auto-injects `DATABASE_URL` into `researchpilot-api`:
  `postgres://researchpilot:<password>@dpg-xxxxxx-a:5432/researchpilot`

### B. Dual Database URL Architecture (Async vs. Sync)
ResearchPilot uses two distinct database drivers:
1. **Async Driver (`asyncpg`)**: Used by FastAPI endpoints and SQLAlchemy async sessions (`app/db/session.py`). Requires `postgresql+asyncpg://` dialect and `ssl=require`.
2. **Sync Driver (`psycopg2`)**: Used by Alembic migrations (`alembic upgrade head`) and container pre-flight connectivity checks (`docker-entrypoint.sh`). Requires `postgresql+psycopg2://` dialect and `sslmode=require`.

### C. Automatic Derivation & Defense-in-Depth
- **Blueprint Injection:** Both `DATABASE_URL` and `SYNC_DATABASE_URL` are linked to `researchpilot-db.connectionString` in `render.yaml`.
- **Dynamic Derivation:** In `app/core/config.py`, if `SYNC_DATABASE_URL` is not provided or points to a stale local address while `DATABASE_URL` is remote, `SYNC_DATABASE_URL` is automatically derived from `DATABASE_URL`.
- **Shell Export:** `backend/docker-entrypoint.sh` exports `SYNC_DATABASE_URL="${SYNC_DATABASE_URL:-$DATABASE_URL}"` before executing Alembic.
- **Fail-Fast Validation:** If `APP_ENV=production`, the application immediately raises a fatal configuration error if `DATABASE_URL` is missing or points to `localhost`, `127.0.0.1`, `::1`, `0.0.0.0`, or port `5433`.
- **Safe Diagnostic Logging:** Startup pre-flight, Alembic, and FastAPI log target host and port (e.g. `host=dpg-dbo48h3m8hqs73fgujrg-a, port=5432`), strictly redacting passwords and user credentials.

