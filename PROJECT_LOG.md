# Project Log — ResearchPilot

## Stage 1: Foundation and Document Ingestion (Completed)

### Milestones Completed
1. **Environment Inspection & Resolution**:
   - Identified Python 3.13.2, Node.js v22.14.0, npm 10.9.2, and Docker version 29.8.0.
   - Diagnosed conflict on standard Windows port 5432 where an unconfigured Windows PostgreSQL service existed.
   - Configured dedicated PostgreSQL 16 instance with native `pgvector` 0.6.0 in WSL Ubuntu environment listening on port 5433 with trusted local authentication.
   - Configured persistent background daemon process to ensure continuous database availability.

2. **Backend Foundation (FastAPI & SQLAlchemy)**:
   - Initialized FastAPI modular structure with decoupled routers, schemas, services, and core settings.
   - Built asynchronous database session manager (`asyncpg` for app runtime, `psycopg2` for Alembic).
   - Designed complete database schema covering all planned stages:
     - `users`
     - `documents`
     - `document_chunks` (with 768-dim `Vector` column)
     - `research_jobs`
     - `research_sources`
     - `research_reports`
     - `report_claims`
     - `research_events`
   - Configured Alembic migrations with custom `pgvector` support and executed initial schema migration successfully (`be4e82129b04_initial_schema`).

3. **Document Ingestion & Provenance Engine**:
   - Implemented `PDFParser` using PyMuPDF (`pymupdf`) for page-by-page text extraction, structural cleaning, and metadata parsing.
   - Built `TextChunker` with configurable token size (~800 tokens) and overlap (~120 tokens), preserving sequential indexing and exact page number provenance.
   - Built `DocumentService` with file validation (extension `.pdf` only, max 25MB, empty file prevention), local storage management, and database transaction orchestration.
   - Implemented RESTful document API endpoints:
     - `POST /api/v1/documents/upload`
     - `GET /api/v1/documents`
     - `GET /api/v1/documents/{id}`
     - `GET /api/v1/documents/{id}/chunks`
     - `GET /api/v1/documents/{id}/status`
     - `DELETE /api/v1/documents/{id}`
     - `GET /api/v1/health`

4. **Frontend Foundation (React + Vite + Tailwind + shadcn/ui)**:
   - Scaffolded pure JavaScript React frontend with Vite (strictly **zero** TypeScript files).
   - Configured Tailwind CSS with clean slate/blue SaaS theme and dark mode capability.
   - Implemented reusable JavaScript shadcn/ui components (`Button`, `Card`, `Badge`, `Progress`, `Table`, `Dialog`, `Tabs`, `ScrollArea`, `Input`).
   - Built responsive UI screens:
     - **Navbar**: Platform navigation with live system readiness indicator.
     - **Dashboard**: High-level platform statistics, vector chunk counters, and recent document feed.
     - **Knowledge Base**: Drag-and-drop PDF uploader, validation error handling, document table with status badges, chunk inspector dialog showing exact page numbers and tokens, and document deletion.

5. **Testing & Verification**:
   - Configured `pytest` with `pytest-asyncio` using `NullPool` isolation for event loops in Python 3.13.
   - Created test suite with 9 backend unit & integration tests covering extraction, chunking, file validation, and API routes.
   - Created Vitest frontend test suite.
   - All tests passing 100%.

---

## Stage 2: RAG Pipeline (Completed)

### Milestones Completed
1. **Provider Abstraction Architecture**:
   - Designed `EmbeddingProvider` abstract interface (`embed_documents`, `embed_query`).
   - Designed `LLMProvider` abstract interface (`generate`, `generate_structured`).
   - Implemented `GeminiEmbeddingProvider` using official `google-genai` SDK with `text-embedding-004` (768 dimensions).
   - Implemented `GeminiProvider` using official `google-genai` SDK (`gemini-2.5-flash`).
   - Implemented `MockEmbeddingProvider` (deterministic 768-dim hash vectors) and `MockLLMProvider` for isolated, reliable offline and CI/CD test execution.
   - Built provider factory with dynamic selection and environment fallback.

2. **Ingestion Embedding Pipeline**:
   - Updated `DocumentService` to automatically generate vector embeddings for every text chunk during PDF ingestion and persist them directly into PostgreSQL `document_chunks.embedding` (`Vector(768)`).

3. **Semantic Vector Retrieval Engine**:
   - Built `RetrievalService` performing cosine similarity search using pgvector's `cosine_distance` (`<=>` operator).
   - Maintained full provenance metadata across all retrieved chunks: `document_id`, `filename`, `page_number`, `chunk_index`, and `similarity_score`.
   - Supported configurable `top_k` and `threshold` filtering.

4. **Document Q&A and Evidence Grounding Service**:
   - Built `DocumentQAService` orchestrating semantic retrieval, missing evidence verification, prompt formulation with strict page-citation requirements, and citation cross-referencing.
   - Explicitly detects and rejects ungrounded queries when evidence is insufficient or below relevance threshold.
   - Parses `[Page X]` citations and correlates them with exact document chunks.

5. **API & Frontend Integration**:
   - Exposed `POST /api/v1/qa/query` for grounded Q&A with citations.
   - Exposed `POST /api/v1/qa/search` for raw ranked chunk inspection.
   - Enhanced the frontend **Knowledge Base** with an interactive "Ask Documents (RAG)" tab displaying synthesized answers, page citation pills, and ranked evidence cards with similarity percentages.

6. **Quality & Regression Testing**:
   - Added `backend/tests/test_retrieval.py` with fixed question set:
     - Verified RBI regulatory compliance query ranks Page 2 #1.
     - Verified AI adoption banking query ranks Page 1 #1.
     - Verified Q&A synthesizes answer with genuine Page 2 citation.
     - Verified unrelated queries trigger explicit missing evidence response with 0 citations.
   - All 11 backend tests pass in 0.68s.

---

## Stage 3: Multi-Agent Engine (Completed)

### Milestones Completed
1. **LangGraph Orchestration Architecture**:
   - Integrated `langgraph` StateGraph workflow with typed `ResearchState`.
   - Implemented `Annotated[List[Dict[str, Any]], operator.add]` state reducers to allow conflict-free parallel state updates.
   - Designed parallel fan-out conditional routing after planning, branching concurrently into Web Research and Document Research.
   - Implemented Evidence Normalizer join node to consolidate and rank multi-modal evidence.

2. **Specialized Intelligence Agents**:
   - **Planner Agent (`PlannerAgent`)**: Generates structured, validated `ResearchPlan` breaking complex queries into 3-5 investigative sub-questions with assigned focus areas and source types.
   - **Web Research Agent (`WebResearchAgent`)**: Interfaces with Tavily API (with verified domain fallbacks), deduplicates by URL, and extracts publication dates.
   - **Document Research Agent (`DocumentResearchAgent`)**: Concurrently executes semantic vector searches across selected PDFs in pgvector, preserving chunk IDs and exact page numbers.
   - **Evidence Normalizer**: Aggregates, validates, and sorts cross-source evidence by relevance score.

3. **Job Management & Persistence**:
   - Implemented `ResearchJobManager` to handle lifecycle tracking (`queued` -> `processing` -> `completed` / `failed`), background asynchronous task execution, milestone event logging (`research_events`), and evidence source persistence (`research_sources`).
   - Exposed REST APIs: `POST /api/v1/research/jobs`, `GET /api/v1/research/jobs`, `GET /api/v1/research/jobs/{id}`, and `GET /api/v1/research/jobs/{id}/events`.

4. **Frontend Research Workspace**:
   - Built **New Research** interface with query textarea, example prompts, depth selectors ("quick", "standard", "deep"), web search toggle, and multi-PDF document selector.
   - Built **Live Agent Execution View** displaying real-time stepper across agents, research plan overview, and live event log timeline.
   - Updated **Dashboard** with research job counters, quick action launchers, and recent inquiries feed.

5. **Automated Testing & Verification**:
   - Built `backend/tests/test_agents.py` testing planner structured output, web research agent, parallel LangGraph execution, conditional routing (web-only, doc-only), and job API lifecycle.
   - All 15 tests pass in 0.90s.

---

## Stage 4: Fact Checking and Report Generation (Completed)

### Milestones Completed
1. **Fact Checker Agent (`FactCheckerAgent`)**:
   - Extracts factual assertions from collected multi-source evidence.
   - Evaluates claims against evidence support without claiming infallible truth.
   - Classifies each claim into: `supported`, `partially_supported`, `unsupported`, or `contradictory`.
   - Associates each claim with an exact evidence quote, citation source, and confidence score.

2. **Report Writer Agent (`ReportWriterAgent`)**:
   - Synthesizes findings into the required 9-section institutional report schema:
     1. Executive summary
     2. Industry overview
     3. Key research findings (with inline citation tags)
     4. Strategic opportunities
     5. Risks and challenges (regulatory, cybersecurity, data sovereignty)
     6. Contradictory findings & divergent perspectives
     7. Future outlook (3-5 years)
     8. Fact-checked claims audit
     9. Supporting evidence & clickable references
   - Strict avoidance of fabricated facts or invented URLs.

3. **Full 5-Agent LangGraph Integration**:
   - Assembled complete pipeline: `START -> planner -> [web_research || document_research] -> evidence_normalizer -> fact_checker -> report_writer -> END`.
   - Updated `ResearchJobManager` to persist the completed report into `research_reports` and individual claims into `report_claims`.

4. **Live Streaming & REST Endpoints**:
   - Built Server-Sent Events (SSE) streaming endpoint: `GET /api/v1/research/jobs/{id}/stream`.
   - Built report retrieval endpoint: `GET /api/v1/research/jobs/{id}/report`.

5. **Frontend Report Viewer UI**:
   - Built `ReportViewer.jsx` displaying the full 9 sections with an interactive Fact-Check Audit Summary bar.
   - Implemented clickable web source links (`target="_blank"`) and document page number badges.
   - Added Markdown export functionality.
   - Connected "View Full Report" CTA directly from the live execution screen.

6. **Automated Testing & Verification**:
   - Added `backend/tests/test_report_generation.py` testing the Fact Checker Agent, Report Writer Agent, and full end-to-end research job execution with PostgreSQL persistence.
   - All 18 backend tests pass in 1.52s. Vitest frontend test suite passes.

---

## Stage 5: Evaluation & Deployment (Completed)

### Milestones Completed
1. **Security & Prompt Injection Defense**:
   - Implemented `SecurityAuditor` in `backend/app/core/security.py` featuring regex pattern neutralization for indirect prompt injections (`Ignore previous instructions`, `System: you are now...`, etc.).
   - Implemented strict untrusted context boundary fencing (`<<<UNTRUSTED_EVIDENCE_BOUNDARY_START>>> ... <<<UNTRUSTED_EVIDENCE_BOUNDARY_END>>>`) ensuring LLMs treat ingested text strictly as data.

2. **RAG Retrieval Quality & Citation Faithfulness Evaluation**:
   - Built comprehensive evaluation test suite in `backend/tests/test_evaluation.py`:
     - Evaluated prompt injection sanitization.
     - Evaluated RAG Precision@K and Recall@K against a multi-page banking/regulatory benchmark dataset:
       - **Recall@3 = 100% (1.00)**.
       - **Precision@3 = 33.3% (0.33)** (1 target page per query out of top-3 retrieved chunks across distinct pages).
     - Evaluated Answer Faithfulness and Citation Correctness: verified 100% of cited pages match real physical document page numbers without hallucination.

3. **Frontend Component & Integration Unit Testing**:
   - Added unit test suite in `frontend/src/__tests__/ui_components.test.jsx` covering Tailwind merge utilities (`cn`), badge variant generators, and button variants.
   - Ran `npm test` (all 4 Vitest unit tests pass in 1.51s).
   - Ran `npm run build` (production Vite build passes with zero errors).

4. **Containerization & Deployment Architecture**:
   - **Backend Containerization**:
     - Built `backend/Dockerfile` with `python:3.13-slim`, C build tools, and system dependencies for PyMuPDF/PostgreSQL.
     - Created `backend/docker-entrypoint.sh` with automated database readiness polling, Alembic migration execution, and Uvicorn server startup.
     - Added `backend/.dockerignore`.
   - **Frontend Containerization**:
     - Built multi-stage `frontend/Dockerfile` (Node 20 Alpine builder -> Nginx Alpine runtime).
     - Configured `frontend/nginx.conf` with gzip compression, client-side SPA routing (`try_files $uri $uri/ /index.html;`), and reverse proxying for `/api/` with buffering disabled for Server-Sent Events (SSE).
     - Added `frontend/.dockerignore`.
   - **Docker Compose Orchestration**:
     - Created root `docker-compose.yml` declaring 3 unified services:
       - `db`: `pgvector/pgvector:pg16` with healthcheck on port 5432.
       - `backend`: FastAPI backend on port 8000, depending on healthy `db`.
       - `frontend`: Nginx serving production bundle on port 3000, depending on `backend`.
     - Validated syntax with `docker-compose config` (passes cleanly).

5. **Documentation & Quality Deliverables**:
   - Created `EVALUATION.md` documenting retrieval metrics, citation accuracy, prompt injection defense, and verification procedures.
   - Updated `README.md` with complete architecture overview, multi-agent diagram, Docker Compose instructions, and API endpoints.
   - Updated `ARCHITECTURE.md` with final multi-agent sequence diagrams, security boundaries, and database entity relationships.

6. **Final Test Suite Run**:
   - Backend: 21 automated tests pass in 1.89s (`pytest -v`).
   - Frontend: 4 tests pass (`npm test`), production build passes (`npm run build`).

---

## Final End-to-End System Verification Audit (Completed)

### Milestones Completed
1. **Live AI Integrations Verification**:
   - Verified provider factory selection: correctly chooses `MockLLMProvider` and `MockEmbeddingProvider` when environment keys are absent, and constructs `GeminiProvider` and `GeminiEmbeddingProvider` when configured.
   - Tested error handling with invalid credentials: confirmed clean HTTP 400 ClientError capture.
   - Verified Tavily search fallback to grounded industry URLs when keys are not configured.
   - Verified PostgreSQL 16 + `pgvector` 0.6.0 with `<=>` cosine distance operator calculations.
   - Verified LangGraph compilation and parallel fan-out routing.

2. **End-to-End Research Scenarios (6 Scenarios Verified)**:
   - Scenario 1 (Both Web + PDF): Full 9-section report generated with verified web URLs and document page provenance; claim audit identified both supported and unsupported claims.
   - Scenario 2 (Web Only): Document Research Agent skipped; references contain only verified web sources.
   - Scenario 3 (PDF Only): Web Research Agent skipped; references contain only PDF page citations.
   - Scenario 4 (No Relevant Documents): Astronomy PDF supplied for banking query; claims flagged as unsupported.
   - Scenario 5 (Empty Sources): Handled gracefully with honest missing evidence disclosure.
   - Scenario 6 (Unrelated Query): Quantum physics query audited against banking PDF; claims flagged as unsupported without hallucinations.

3. **In-Depth RAG Benchmark Metrics**:
   - Evaluated 5-page corpus across 10 queries (8 in-domain, 2 out-of-domain).
   - Results: **MRR: 0.9167**, **Precision@1: 0.8750**, **Recall@3: 0.9375**, **nDCG@3: 0.8891**, **Retrieval Failure Rate: 0.0%**, **Out-of-Domain Rejection Rate: 100.0%**.

4. **Security Hardening & Format Integrity**:
   - Fixed PDF format vulnerability: added `%PDF-` magic header verification and PyMuPDF `doc.is_pdf` validation to reject spoofed HTML/EXE files disguised as PDFs.
   - Verified path traversal neutralization, oversized file rejection (>25MB), SQL injection parameterized bindings, zero API key leakage in responses, and restricted CORS origins.

5. **Alembic Fresh Migration Stabilization**:
   - Fixed fresh database migration failure: added `CREATE EXTENSION IF NOT EXISTS vector;` to initial migration and configured `alembic/env.py` to respect dynamic database URLs. Tested successfully on a fresh database.

6. **Dual-Mode Provider Architecture (Mock Mode vs Live AI Mode)**:
   - Configured explicit `PROVIDER_MODE` (`auto`, `mock`, `live`).
   - Hardened error handling: live remote API failures (HTTP 400/401/403/429) raise typed `ProviderAuthenticationError` or `ProviderQuotaError` and fail research jobs transparently rather than silently masking failures with mock output.
   - Built deterministic mock structured generator for `ResearchPlan`, `ClaimsExtractionResult`, and `ResearchReportSchema` clearly prefixed with `[MOCK]`.
   - Created safe diagnostic endpoint `GET /api/v1/system/status` exposing provider names, active mode, and key presence without exposing raw secrets.
   - Enhanced frontend UI (Navbar, New Research, Report Viewer) with live provider mode pills and simulation disclaimer banners.
   - Verified Scenarios A (Mock Mode without keys), B (Invalid Gemini key failure), and C (Invalid Tavily key failure) with 100% test pass.

7. **Docker Status Assessment**:
   - `docker-compose config` validated with zero syntax errors.
   - Docker daemon was inactive on host; runtime deployment accurately reported as PARTIAL / NOT VERIFIED for live execution while compose definitions are verified.



