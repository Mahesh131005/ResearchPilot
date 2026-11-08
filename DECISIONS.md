# Architectural & Engineering Decisions — ResearchPilot

## ADR-001: Pure JavaScript for Frontend (No TypeScript)
- **Context**: The master prompt strictly specified JavaScript (ES6+) and JSX without `.ts` or `.tsx` files.
- **Decision**: Vite was configured for React JS. shadcn/ui primitives were implemented using JavaScript, `clsx`, `tailwind-merge`, and `class-variance-authority`. All application files use `.js` and `.jsx`.

## ADR-002: Dual-Driver Database Configuration
- **Context**: FastAPI utilizes modern Python `asyncio` for high concurrency, while Alembic operates synchronously.
- **Decision**: The platform uses `asyncpg` via `postgresql+asyncpg://` for application request handling and `psycopg2-binary` via `postgresql+psycopg2://` for synchronous Alembic migrations.

## ADR-003: Port 5433 Isolation for PostgreSQL + pgvector
- **Context**: The development environment had a pre-existing Windows PostgreSQL service occupying port 5432 that lacked the required `pgvector` extension and had restricted credentials.
- **Decision**: Configured a dedicated PostgreSQL 16 instance with native `pgvector` 0.6.0 running in WSL Ubuntu on port 5433. A persistent daemon process maintains the service.

## ADR-004: Sentence-Aware Chunking with Exact Page Provenance
- **Context**: RAG systems frequently lose citation provenance if documents are flattened into continuous text before chunking.
- **Decision**: `TextChunker` chunks documents per page or preserves page boundaries. Every chunk explicitly records `page_number` and sequential `chunk_index`. This guarantees that in subsequent stages, RAG citations point to genuine, verifiable document pages without hallucinated citations.

## ADR-005: NullPool for Test Isolation in Python 3.13
- **Context**: In Python 3.13 on Windows, `pytest-asyncio` allocates a distinct event loop per test function by default. Reusing pooled database connections from a closed event loop causes `RuntimeError: Event loop is closed`.
- **Decision**: Configured `NullPool` in `tests/conftest.py` so that test connections are opened and cleanly closed within the scope of each test's individual event loop.

## ADR-006: Provider Abstraction with Deterministic Offline Harness
- **Context**: System must support multiple LLM/Embedding providers (Gemini, OpenAI, Anthropic) while running reproducible tests without consuming API credits or depending on external internet access.
- **Decision**: Implemented `EmbeddingProvider` and `LLMProvider` abstract classes. Concrete `GeminiEmbeddingProvider` and `GeminiProvider` power production, while `MockEmbeddingProvider` (deterministic 768-dim hash vectors) and `MockLLMProvider` guarantee that all RAG retrieval and citation logic is verified deterministically in CI/CD without third-party API dependencies.

## ADR-007: Cosine Distance via pgvector (<=>) with Missing Evidence Guardrails
- **Context**: Document RAG systems often hallucinate answers when user questions are outside the knowledge base domain.
- **Decision**: Utilized pgvector's `<=>` (cosine distance) with a configurable `SIMILARITY_THRESHOLD`. If no chunks meet the threshold, `DocumentQAService` halts generation and emits an explicit `has_sufficient_evidence=False` response with 0 fabricated citations.

## ADR-008: LangGraph State Graph with Conflict-Free Annotated Reducers
- **Context**: When executing Web Research and Document Research agents in parallel, concurrent updates to shared state lists (`evidence`, `events`) cause race conditions or state overwriting.
- **Decision**: Modeled `ResearchState` using `Annotated[List[Dict[str, Any]], operator.add]` for list accumulators. This allows LangGraph's parallel fan-out branches to return incremental evidence fragments that merge deterministically into the global state before reaching the Evidence Normalizer node.

## ADR-009: Fact-Checking Claim Audit Schema with Strict Evidence Grounding
- **Context**: Large language models can state inaccurate assertions with high confidence. The platform must separate verifiable evidence support from ungrounded claims.
- **Decision**: Engineered `FactCheckerAgent` to decompose syntheses into atomic claims and classify each into `supported`, `partially_supported`, `unsupported`, or `contradictory`. Each claim is required to pair with a verbatim evidence quote and verified citation tag (`[Page X]` or domain URL).

## ADR-010: Multi-Stage Containerization with SSE Non-Buffering Nginx Proxy
- **Context**: Research reports take time to synthesize through multiple agents. Users need real-time streaming progress over Server-Sent Events (SSE), and the application must be easily deployable anywhere.
- **Decision**: Built a multi-stage frontend Dockerfile with Nginx Alpine serving the production SPA and reverse-proxying `/api/` to FastAPI on port 8000. Nginx is configured with `proxy_buffering off;` and `proxy_cache off;` so that SSE milestone events are streamed to the browser without intermediate buffer delays.

## ADR-011: Strict PDF Magic Byte Header and PyMuPDF `is_pdf` Format Verification
- **Context**: File extension validation (`.pdf`) alone allows attackers to rename malicious HTML, JavaScript, or executable binaries to `.pdf` and bypass simple extension checks.
- **Decision**: Implemented two-tier validation: (1) `DocumentService.validate_upload` checks that the raw file stream begins with `%PDF-` magic header bytes before saving to disk; (2) `PDFParser.extract_text_and_metadata` validates `doc.is_pdf is True` upon opening to prevent non-PDF formats (HTML, EPUB, XPS) from being parsed as valid PDF documents.

## ADR-012: Dynamic Alembic Database URL Resolution and Vector Extension Pre-migration
- **Context**: When initializing fresh, empty test databases or deploying in staging environments, `alembic upgrade head` failed because: (1) `alembic/env.py` unconditionally overwrote dynamically configured database URLs with `settings.SYNC_DATABASE_URL`; and (2) PostgreSQL extensions are per-database, so tables with `Vector(768)` failed before the `vector` extension was enabled.
- **Decision**: Updated `alembic/env.py` to only fall back to `settings.SYNC_DATABASE_URL` if `sqlalchemy.url` was not explicitly supplied, and added `op.execute("CREATE EXTENSION IF NOT EXISTS vector;")` at the start of `be4e82129b04_initial_schema.py` `upgrade()`.

## ADR-013: Explicit Dual-Mode Architecture (Mock vs Live) with Non-Masking Failure Propagation
- **Context**: Relying on generic exception handling in agents and search services caused invalid, expired, or missing API keys in Live Mode to silently fall back to mock data, creating false illusions of successful live research.
- **Decision**: Implemented explicit `PROVIDER_MODE` (`auto`, `mock`, `live`). In Live Mode, remote failures (HTTP 400/401/403/429) raise typed `ProviderAuthenticationError`, `ProviderQuotaError`, or `ProviderAPIError` that explicitly mark jobs as `failed` with clear diagnostics. Mock Mode is strictly transparent, prefixing all simulated plans, claims, and reports with `[MOCK]` to ensure zero confusion between simulated and live intelligence.

## ADR-015: Rate Limiting, Atomic Concurrency Locking, and Idempotent Usage Telemetry (Stage 2)
- **Context**: Allowing multi-user access without rate limiting or provider resource controls exposes the platform to runaway Gemini and Tavily API bills, malicious scraping, and concurrent job resource exhaustion.
- **Decision**:
  1. **Configurable Tier-Based Limits**: Established configurable rate limits and quotas for Free, Pro, and Admin tiers in `Settings`, with per-user overrides supported via a new `user_quotas` database table. Free tier defaults: 5 submissions/hour, 5 jobs/day, 100 jobs/month, 1 concurrent job, 5 Tavily searches/job.
  2. **Atomic Row-Level Locking (`SELECT ... FOR UPDATE`)**: Rather than adding external queue infrastructure or Redis for concurrency control, the job submission pipeline acquires an atomic row lock on the user's `User` record inside a PostgreSQL transaction (`select(User.id).where(User.id == user.id).with_for_update()`). This serializes concurrent job launches for that user, providing 100% thread-safe and process-safe concurrency and rate limit checks with zero race conditions.
  3. **Standard HTTP 429 Responses with Retry-After**: When any quota (hourly, daily, monthly, concurrency) is reached, the backend returns `HTTP 429 Too Many Requests` with a standard `Retry-After: <seconds>` header and descriptive JSON payload containing the exceeded limit type, current usage, and reset guidance.
  4. **Idempotent Job Retries & Double-Counting Prevention**: `ResearchJobCreate` supports an optional `client_token` (or `X-Idempotency-Key` header). If a job with that token already exists for the user, the existing job is returned immediately with `HTTP 201 Created` without decrementing user quotas or creating duplicate executions.
  5. **Granular, Idempotent Provider Usage Telemetry**: Implemented `provider_usage_events` table recording every Gemini LLM call, Gemini embedding generation, and Tavily search call with `user_id`, `job_id`, `input_tokens`, `output_tokens`, `total_tokens`, `embedding_tokens`, `search_depth`, and `is_estimated`. Token metrics capture actual provider usage metadata from `response.usage_metadata` where available; if unavailable (such as embedding API limitation or offline mock runs), the limitation is recorded explicitly with `is_estimated=True, usage_metadata_available=False`. Usage events use unique scoped idempotency keys (`idempotency_key=f"gemini:{scope}:{model}:{hash}"`) to prevent double-counting on network retries.
  6. **Per-Job Tavily Search Ceilings**: In `WebResearchAgent`, web searches are capped by the user's tier ceiling (e.g. 5 searches per research job). If the research plan generates more sub-questions than the ceiling, the agent stops further searches and logs a quota ceiling notice, allowing the research report to synthesize cleanly from available evidence without failing the job.
  7. **Frontend Usage & Quota Telemetry UI**: Added `/usage` route and navbar link in pure JavaScript/JSX featuring progress indicators for daily, monthly, and hourly limits, real-time concurrency status badges, Gemini and Tavily token consumption breakdowns, and a paginated audit log of usage events. In `NewResearch.jsx`, 429 quota errors render dedicated banners with direct links to the Quotas dashboard.

## ADR-016: Intentional Deferral of Full Monetary Cost Management & Implementation of Emergency Billable Switch
- **Context**: Full financial cost management (pricing catalogs, micro-dollar tracking, global spending reservations, financial ledgers, Stripe billing) introduces significant premature complexity during early beta development where traffic is controlled and Gemini usage is restricted to free tiers.
- **Decision**:
  1. **Intentional Deferral**: Full monetary cost management is formally deferred to Stage 6 (after research quality and beta client expansion). The following deferred features are documented to be implemented when scaling:
     - Monetary cost estimation per job/user
     - Configurable provider pricing matrix
     - Atomic monetary budget reservations
     - Daily/monthly global spending limits and automated alerts
     - Financial ledger, cost reconciliation, and admin spending dashboards
     - Stripe or subscription payments
  2. **Essential Safety Safeguards Preserved**: Stage 2's rate limiting, user quotas (hourly/daily/monthly/concurrent), Tavily per-job ceilings, and actual token telemetry remain fully active and enforced on the backend.
  3. **Emergency Billable Kill-Switch (`BILLABLE_OPERATIONS_ENABLED`)**: Implemented a backend configuration switch (`BILLABLE_OPERATIONS_ENABLED: bool = True`). When set to `False`, the backend immediately blocks any operations that could incur external billable API charges (returning HTTP 503), while preserving full access to existing documents, past reports, and offline mock workflows.

## ADR-017: Multi-Document Scoped Semantic Search, Query Reformulation & Resilience Engine (Stage 3)
- **Context**: Prior to Stage 3, Document Research was constrained to single-document queries and lacked strict user tenancy filtering in vector search. Additionally, long conversational sub-questions were passed directly to retrieval engines, reducing precision, and partial search or network failures crashed the entire multi-agent workflow.
- **Decision**:
  1. **Multi-Document & User-Isolated Semantic Retrieval**: Updated `RetrievalService.search` to support `document_ids: List[uuid.UUID]` via SQL `.in_()`, allowing users to select multiple documents for a research job. Always enforce `Document.user_id == user_id` to guarantee 100% cross-user isolation in vector space.
  2. **Search Query Reformulation in Planner**: Extended `SubQuestion` schema with an optimized `search_query` field containing 3 to 6 targeted keywords. The Planner Agent reformulates long questions into focused search terms, dramatically boosting retrieval precision on both Tavily and pgvector.
  3. **Resilient Document Retrieval Fallback**: `DocumentResearchAgent` first attempts vector retrieval using the optimized `search_query`. If zero chunks are returned (due to strict similarity thresholds), it automatically falls back to the original full question text before concluding no evidence was found.
  4. **Web Research Resilience & URL Deduplication**: `WebResearchAgent` wraps individual web searches in resilient error handling. If a single search encounters an API hiccup or rate limit, it degrades gracefully and continues with remaining sub-questions rather than halting the job. URLs are canonicalized (stripping anchors and trailing slashes) to prevent duplicate evidence.
  5. **Transparent Zero-Evidence Reporting**: When zero matching evidence meets relevance thresholds across both web and document sources, `ReportWriterAgent` generates a formal, transparent "Insufficient Evidence" report with missing evidence disclosures rather than hallucinating speculative findings or throwing uncaught exceptions.
  6. **Automated Quantitative Benchmark Suite**: Expanded `test_evaluation.py` with executable metrics for Precision@K, Recall@K, Mean Reciprocal Rank (MRR >= 0.85), Normalized Discounted Cumulative Gain (nDCG >= 0.80), multi-doc isolation, and zero-evidence reporting.

## ADR-018: VS Code Extension Client Architecture, SecretStorage Security & SSE Integration (Stage 4)
- **Context**: To allow developers and researchers to use ResearchPilot inside their IDE without switching to a web browser, a VS Code extension was needed. The extension must share the backend without duplicating research logic, respect all multi-user rate limits and quotas, and adhere to strict security constraints (JavaScript only, no TypeScript, zero credential exposure in webviews).
- **Decision**:
  1. **Pure JavaScript Extension Architecture**: Built `vscode-extension/` entirely in JavaScript (ES6+ / CommonJS for Node.js runtime) with zero TypeScript dependencies.
  2. **VS Code SecretStorage Token Management**: Implemented `TokenManager` utilizing `context.secrets` to persist JWT access and refresh tokens directly in the user's OS keychain. Tokens are never passed to webview JavaScript or stored in unencrypted settings.
  3. **Client-Side Refresh Token Rotation**: `ResearchPilotApiClient` intercepts `HTTP 401 Unauthorized` responses and automatically triggers `POST /api/v1/auth/refresh` using the stored refresh token. If successful, it persists the rotated token pair and transparently retries the failed request.
  4. **Backend Rate-Limit & Kill-Switch Diagnostic Handling**: The extension captures `HTTP 429` (parsing the `Retry-After` header and structured quota limits) and `HTTP 503` (emergency billable shutoff), providing immediate and actionable guidance to the user.
  5. **Real-Time SSE Execution Streaming**: Implemented `SSEResearchStream` to parse chunked Server-Sent Events from `GET /api/v1/research/jobs/{id}/stream`, driving a live multi-agent execution stepper in the sidebar.
  6. **Editor Selection Research with Explicit Consent**: Created the `researchpilot.researchSelection` context menu command, which extracts highlighted editor text and presents an explicit modal confirmation dialog before dispatching the query, preventing inadvertent code leaks.
  7. **Interactive Report Webview & One-Click Markdown Export**: Implemented `ReportPanel` (WebviewPanel) rendering interactive fact-checked claims tables, contradictory findings callouts, and page-level citations, accompanied by `formatReportAsMarkdown` for one-click saving to the active workspace.
  8. **Zero-Dependency Automated Testing**: Created 16 unit tests utilizing Node.js's native `node:test` runner, verifying API client normalization, token storage, SSE parsing, and Markdown serialization in ~130ms.

## ADR-019: Production Readiness, Health Probes, Security Middleware, Prometheus Telemetry & Scaling Architecture (Stage 5)
- **Context**: In transitioning ResearchPilot from feature-complete development to production readiness, the service required standard operational probes (Kubernetes/ECS readiness and liveness), OWASP-compliant security headers, request size limits against memory exhaustion, system observability and Prometheus metrics, and a documented scaling topology with Docker Compose resource boundaries.
- **Decision**:
  1. **Liveness & Readiness Probes**: Implemented `GET /api/v1/health` (lightweight liveness) and `GET /api/v1/health/ready` (readiness probe validating PostgreSQL connection pool, upload directory write permissions, billable operations state, and provider mode). Returns HTTP 200 when ready, HTTP 503 when degraded.
  2. **Security & Request Size Middleware**: Implemented ASGI middleware in `app/main.py` enforcing:
     - 30MB payload ceiling (`MAX_REQUEST_BODY_SIZE_MB = 30`), rejecting oversized bodies with `HTTP 413 Content Too Large` before buffer exhaustion.
     - OWASP security headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`.
  3. **Operational Telemetry & Prometheus Exposition**: Implemented `GET /api/v1/system/metrics` exposing uptime, process memory RSS in MB, active/completed/failed jobs, document and chunk counts, token usage (input/output/total), and Tavily search counts in both JSON and Prometheus format (`?format=prometheus` or `Accept: text/plain`).
  4. **Redis Queue & Infrastructure Scaling**: Added Redis 7 Alpine to `docker-compose.yml` with healthchecks, configured `REDIS_URL` in backend core settings, and established container CPU/memory resource limits across all services.
  5. **Comprehensive Scaling & Security Documentation**: Published `docs/SCALING_STRATEGY.md` and `docs/SECURITY_AND_PRIVACY.md` detailing connection pooling, worker autoscaling criteria, graceful shutdown (15s drain), untrusted evidence boundaries, and token lifecycles.
  6. **Automated Verification**: Added `backend/tests/test_production_readiness.py` covering probes, headers, payload limits, and Prometheus metrics, bringing backend test suite to 61/61 passing.

## ADR-020: Cost Management, Atomic Budget Reservations, Versioned Provider Pricing & Stripe Monetization (Stage 6)
- **Context**: While Stage 2 provided token and search counters, commercial sustainability requires precise monetary cost accounting, versioned provider pricing, atomic budget reservations to prevent concurrent double-spending, global spending limits to protect system budgets, user credit wallets, and payment gateway integration.
- **Decision**:
  1. **Versioned Provider Pricing (`ProviderPricing`)**: Created a database model and administration endpoints to configure and version provider pricing rates (Gemini input/output tokens, text embeddings, and Tavily searches) rather than assuming hardcoded provisional rates.
  2. **Atomic Budget Reservation Protocol**: Before executing a research inquiry, `BillingService.reserve_job_budget` acquires a PostgreSQL row-level lock (`SELECT ... FOR UPDATE`) on the user's `UserWallet` and holds an estimated reservation ($0.05). If balance is insufficient, the API returns `HTTP 402 Payment Required`, preventing concurrent jobs from double-spending.
  3. **Closed-Loop Cost Reconciliation**: Upon workflow completion or failure, `BillingService.reconcile_job_cost` calculates exact itemized costs from all associated `ProviderUsageEvent` records, updates `ResearchJob.cost_usd`, releases the reservation hold, and refunds any excess balance or charges overage.
  4. **Global System Spending Ceilings**: Enforced global daily (`$50.00`) and monthly (`$500.00`) spending caps. When reached, an automated circuit breaker rejects new billable jobs with `HTTP 503`, protecting platform infrastructure from runaway billing.
  5. **Double-Entry Financial Ledger (`CostLedgerEntry`)**: Recorded all balance movements (`credit_grant`, `reservation_hold`, `job_settlement`, `stripe_payment`) with before/after balances, descriptions, and idempotency keys.
  6. **Dual-Mode Stripe Billing**: Built `create_checkout_session` and `process_stripe_webhook_event` supporting live Stripe Checkout (with cryptographic signature verification) and deterministic mock simulation for continuous integration and offline testing.
  7. **Frontend & VS Code Client Integration**: Built the React `Billing.jsx` dashboard (wallet cards, top-up buttons, pricing matrix, and ledger table) and updated VS Code extension error formatting for `HTTP 402 Payment Required`.

## ADR-021: Final Consolidation, Security Hardening, Wire-Level Integration & Release Readiness
- **Context**: The six development stages delivered comprehensive capabilities across the backend, web UI, and VS Code extension, but several edge-case vulnerabilities, benchmark gaps, and cross-tier integration verifications remained deferred.
- **Decision**:
  1. **Chunked Request Stream Protection**: Hardened `security_and_size_middleware` in `backend/app/main.py` by intercepting chunked streaming request bodies and tracking cumulative bytes, rejecting payloads exceeding `MAX_REQUEST_BODY_SIZE_MB` with `HTTP 413` before buffer exhaustion.
  2. **Committed Global Spend Accounting**: Hardened `BillingService.check_global_budget_limits` to sum settled ledger spend plus active in-flight wallet reservations (`sum(UserWallet.reserved_usd)`), preventing concurrent requests from blowing past daily caps before settlement.
  3. **VS Code Webview Content-Security-Policy & URL Sanitization**: Enforced strict CSP (`default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';`) on all extension webviews, blocked `javascript:...` links, and added a 20,000-character upper bound on selected-text research inquiries.
  4. **Live Wire-Level TCP Integration Testing**: Implemented native Node.js TCP integration tests verifying live HTTP wire protocol, token lifecycle, 401 automatic refresh rotation over the wire, and chunked SSE streaming.
  5. **Expanded Multi-Category Evaluation Suite**: Enhanced `test_evaluation.py` and `EVALUATION.md` to compute Precision@1, Precision@3/5, Recall@1/3/5, MRR (>= 0.85), and nDCG (>= 0.80) across single-doc, cross-section, ambiguous, zero-evidence, and fact-checker contradiction audits.
  6. **Release Artifacts**: Published `FINAL_AUDIT.md`, `FINAL_TEST_REPORT.md`, `RELEASE_CHECKLIST.md`, and `KNOWN_LIMITATIONS.md`. Verified all 109 automated tests passing with zero failures.










