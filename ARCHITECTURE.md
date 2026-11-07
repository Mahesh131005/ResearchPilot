# System Architecture — ResearchPilot

## 1. Overview
ResearchPilot is an institutional-grade, multi-agent AI research platform designed to automate deep research, synthesize evidence from uploaded PDFs and live web sources, verify claims against retrieved facts, and generate cited intelligence reports.

---

## 2. Layered Architecture

```
+-------------------------------------------------------------------------+
|                       Presentation Layer (Frontend)                     |
|  - Vite + React 18 (Pure JavaScript & JSX, NO TypeScript)               |
|  - Tailwind CSS + shadcn/ui JS components                               |
|  - React Router DOM + Axios HTTP Client                                 |
+------------------------------------+------------------------------------+
                                     | HTTP / SSE
                                     v
+-------------------------------------------------------------------------+
|                         API Layer (FastAPI)                             |
|  - Asynchronous REST Routers (/documents, /qa, /research, /health)      |
|  - Request & Response Validation (Pydantic v2)                          |
|  - Global CORS & Exception Middleware                                   |
+------------------------------------+------------------------------------+
                                     |
             +-----------------------+-----------------------+
             |                                               |
             v                                               v
+----------------------------+             +------------------------------+
|     Intelligence Layer     |             |          Data Layer          |
| - LangGraph Workflow Engine|             | - PostgreSQL 16              |
| - Planner Agent            |             | - pgvector 0.6.0 (768 dims)  |
| - Web Research (Tavily)    |             | - PyMuPDF (fitz) parser      |
| - Document RAG Agent       |             | - Alembic Database Migration |
| - Fact Checker Agent       |             +------------------------------+
| - Report Writer Agent      |
| - Provider Abstractions    |
+----------------------------+
```

---

## 3. Multi-Agent Workflow Architecture

ResearchPilot uses **LangGraph** to coordinate 5 specialized autonomous agents through typed states and parallel fan-out routing:

```mermaid
flowchart TD
    StartNode([Start Research Job]) --> Planner[1. Planner Agent]
    
    Planner -->|Evaluate Query & Depth| RoutingDecision{Execution Route}
    RoutingDecision -->|Web + Docs| ParallelFork[Parallel Branching]
    RoutingDecision -->|Web Only| WebAgent[2. Web Research Agent]
    RoutingDecision -->|Docs Only| DocAgent[3. Document Research Agent]

    ParallelFork --> WebAgent
    ParallelFork --> DocAgent

    WebAgent -->|Annotated Reducer Merging| EvidenceJoin[Evidence Normalizer Node]
    DocAgent -->|Annotated Reducer Merging| EvidenceJoin

    EvidenceJoin --> FactChecker[4. Fact Checker Agent]
    FactChecker -->|Claim-by-Claim Verification| ReportWriter[5. Report Writer Agent]
    ReportWriter --> EndNode([Persist Report & Complete])
```

### Agent Roles & Responsibilities

1. **Planner Agent (`PlannerAgent`)**:
   - Decomposes the research topic into 3–5 targeted sub-questions.
   - Categorizes information channels (`web`, `document`, or `both`).
   - Produces structured Pydantic `ResearchPlan`.

2. **Web Research Agent (`WebResearchAgent`)**:
   - Executes targeted searches against the Tavily API.
   - Normalizes snippet contents, deduplicates URLs, and extracts publication dates.
   - Strictly enforces real web source URLs.

3. **Document Research Agent (`DocumentResearchAgent`)**:
   - Converts sub-questions into 768-dimensional query embeddings.
   - Performs cosine similarity search (`<=>`) in PostgreSQL via `pgvector`.
   - Preserves exact originating page numbers (`[Page X]`) and chunk IDs.

4. **Fact Checker Agent (`FactCheckerAgent`)**:
   - Extracts factual assertions from synthesized evidence.
   - Classifies claims into: `supported`, `partially_supported`, `unsupported`, or `contradictory`.
   - Never assumes LLM infallibility; ties every claim to concrete evidence chunks.

5. **Report Writer Agent (`ReportWriterAgent`)**:
   - Compiles findings into an institutional 9-section report.
   - Generates clickable citation pills linking directly to web URLs and PDF pages.
   - Flags limitations, risks, and contradictory viewpoints.

---

## 4. Entity-Relationship Model (ERD)

```mermaid
erDiagram
    users ||--o{ documents : owns
    users ||--o{ research_jobs : launches
    documents ||--|{ document_chunks : contains
    research_jobs ||--o{ research_sources : collects
    research_jobs ||--o| research_reports : generates
    research_jobs ||--o{ research_events : emits
    research_reports ||--o{ report_claims : verifies

    users {
        uuid id PK
        string email
        string hashed_password
        datetime created_at
    }

    documents {
        uuid id PK
        uuid user_id FK
        string filename
        integer file_size
        integer page_count
        string status
        datetime created_at
    }

    document_chunks {
        uuid id PK
        uuid document_id FK
        integer chunk_index
        integer page_number
        text chunk_text
        vector embedding "768-dim"
        integer token_count
    }

    research_jobs {
        uuid id PK
        uuid user_id FK
        text query
        string depth
        string status
        jsonb plan
        datetime created_at
    }

    research_sources {
        uuid id PK
        uuid job_id FK
        string source_type "web | document"
        string title
        string url
        integer page_number
        text snippet
        float relevance_score
    }

    research_reports {
        uuid id PK
        uuid job_id FK
        string title
        text executive_summary
        jsonb sections
        datetime created_at
    }

    report_claims {
        uuid id PK
        uuid report_id FK
        text claim_text
        string status "supported | partially_supported | unsupported | contradictory"
        text evidence_quote
        string source_type
        string citation_ref
    }

    research_events {
        uuid id PK
        uuid job_id FK
        string event_type
        string stage
        text message
        datetime created_at
    }
```

---

## 5. Security & Isolation Architecture

To safeguard multi-agent workflows from untrusted document uploads and external web content, ResearchPilot applies a **Defense-in-Depth** model:

```
[ External PDF Upload / Scraped Web Text ]
                   │
                   ▼
     ┌────────────────────────────┐
     │      Security Auditor      │
     │  (Regex Injection Filter)  │
     └─────────────┬──────────────┘
                   │ Neutralizes "Ignore previous instructions", "System:", etc.
                   ▼
     ┌────────────────────────────┐
     │ Boundary Enclosure Fencing │
     │  <<<UNTRUSTED_EVIDENCE...  │
     └─────────────┬──────────────┘
                   │ Isolates text as inert evidence data
                   ▼
     ┌────────────────────────────┐
     │ LLM Intelligence Pipeline  │
     └────────────────────────────┘
```

---

## 6. Provider Abstraction Pattern

The application does not couple directly to any single proprietary LLM. All intelligence interactions operate via abstract base interfaces:

- **`LLMProvider`**:
  - `generate(prompt, system_instruction, temperature) -> str`
  - `generate_structured(prompt, schema, system_instruction, temperature) -> BaseModel`
- **`EmbeddingProvider`**:
  - `embed_documents(texts: List[str]) -> List[List[float]]`
  - `embed_query(text: str) -> List[float]`

Current concrete implementations:
- `GeminiProvider` (`gemini-2.5-flash`)
- `GeminiEmbeddingProvider` (`text-embedding-004`, 768 dims)
- `MockLLMProvider` (deterministic offline testing)
- `MockEmbeddingProvider` (deterministic 768-dim hash vector)
