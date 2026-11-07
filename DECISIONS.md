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



