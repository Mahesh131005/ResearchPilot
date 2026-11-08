# ResearchPilot — Known Limitations & Operational Boundaries

This document details known operational boundaries, design trade-offs, and provisional configurations within ResearchPilot.

---

## 1. Provider Pricing & Free-Tier Quotas

### Gemini API Rate Limits
- Under Google Gemini's free tier, requests are constrained by strict Requests-Per-Minute (RPM) and Requests-Per-Day (RPD) ceilings (typically 15 RPM for free models).
- In high-throughput beta environments, exceeding provider quotas results in HTTP 429 errors from Google's endpoints.
- **Safeguard**: ResearchPilot implements backend quota tracking and exponential backoff retry boundaries. When provider rate limits are encountered, operations fail cleanly with explanatory messages rather than executing uncontrolled retry loops.

### Tavily Web Search Limits
- ResearchPilot limits Tavily searches to 5 requests per research job by default.
- If Tavily API quota is exhausted, the research workflow continues using document RAG evidence and flags that web evidence was incomplete.

---

## 2. Billing & Stripe Integration

### Test Mode vs. Live Production
- The repository is configured by default for **Stripe Test Mode** (`sk_test_...`).
- Test mode simulates balance recharges ($5.00, $15.00, $50.00) and emits simulated webhook events (`checkout.session.completed`).
- **Production Transition**:
  - Requires completing Stripe Merchant KYC verification.
  - Requires configuring a public HTTPS webhook endpoint with Stripe signature verification (`STRIPE_WEBHOOK_SECRET`).
  - Automated refunds or chargebacks must be handled through the Stripe Dashboard or administrative settlement APIs.

### Currency Precision
- All ledger balances and pricing calculations are tracked in USD with 4 to 6 decimal places (`Numeric(12, 4)` and `Decimal("0.000001")`).
- Multi-currency conversion (e.g., EUR, GBP, INR) is not natively implemented; all transactions settle in USD.

---

## 3. Storage & Multi-Replica Scaling

### Local File Storage vs. Object Storage
- Document PDF uploads are stored on the local filesystem (`backend/uploads/`) by default.
- In a horizontally scaled multi-pod Kubernetes deployment, local storage must be replaced with shared cloud object storage (e.g., AWS S3, Google Cloud Storage, or Azure Blob Storage) via an S3-compatible driver to ensure all backend replicas have access to uploaded PDFs.

### Redis Caching & Distributed Synchronization
- Docker Compose includes a single-node Redis service.
- Single-instance developer deployments use PostgreSQL row-level locking (`SELECT ... FOR UPDATE`) for atomic rate limiting and wallet reservations, ensuring complete data consistency without requiring Redis.
- For high-concurrency multi-node clusters with KEDA autoscaling, Redis Cluster should be enabled for distributed rate limiting and transient SSE pub/sub messaging.

---

## 4. RAG Retrieval & Document Processing

### Vector Dimensionality
- The pgvector schema is indexed for **768-dimensional embeddings** matching Google Gemini's `text-embedding-004` model and ResearchPilot's deterministic local mock embedding generator.
- Changing embedding models (e.g., OpenAI `text-embedding-3-small` at 1536 dims) requires an Alembic migration to update the column dimension.

### Document Format Support
- The current ingestion engine strictly validates and processes PDF documents via PyMuPDF (`fitz`).
- Ingestion of Microsoft Word (`.docx`), plain Markdown, or web HTML files requires pre-converting to PDF or implementing dedicated text extractor adapters.

---

## 5. Client Platforms

### Frontend Framework
- The frontend web application is intentionally authored in pure **JavaScript and JSX** without TypeScript, in strict adherence to project architectural constraints.
- Build tooling uses Vite with Vitest for testing and Tailwind CSS for styling.

### VS Code Extension
- The VS Code extension runs on standard VS Code API (`vscode.workspace`, `vscode.window`, `vscode.authentication`).
- External link navigation within webviews is routed through VS Code's trusted external browser opener rather than rendering web frames inside extension webviews, ensuring strict Content Security Policy compliance.

