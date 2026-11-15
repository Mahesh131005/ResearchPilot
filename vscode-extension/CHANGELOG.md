# Change Log

All notable changes to the "ResearchPilot" extension will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-11-08

### Added
- **Activity Bar & Interactive Sidebar**:
  - Dedicated primary sidebar panel for research query authoring, active execution tracking, and research history retrieval.
  - Native VS Code Webview with secure Content-Security-Policy (CSP) enforcing strict local asset loading.
- **Multi-Agent Orchestration**:
  - Transparent execution progress across 5 specialized agents: Planner Agent, Web Research Agent (Tavily), Document Research Agent (pgvector RAG), Evidence Normalizer, Fact Checker, and Report Writer.
  - Live milestone telemetry streamed over Server-Sent Events (SSE).
- **Interactive Research Report Viewer**:
  - Rich dedicated editor tab (`ReportPanel`) displaying Executive Summaries, Key Findings, Methodology Breakdown, and Grounded Citations.
  - Interactive **Fact-Checked Claims Audit Table** categorizing claim verdicts (`SUPPORTED`, `PARTIALLY_SUPPORTED`, `CONTRADICTORY`, `UNSUPPORTED`), confidence ratings, and direct source quotes.
  - Dedicated **Contradictory Findings** view to highlight empirical discrepancies between sources.
- **Editor Context Menu Integration**:
  - `ResearchPilot: Research Selected Text` command accessible from the editor right-click menu with explicit confirmation to protect code privacy.
- **Workspace Export**:
  - Single-click export of structured research reports to workspace Markdown (`.md`) files with clean frontmatter and bibliography tables.
- **Enterprise Authentication & Token Security**:
  - Zero plain-text token exposure: access and refresh JWTs are securely persisted in VS Code's native OS-level `SecretStorage`.
  - Automatic token rotation upon HTTP 401 expiration.
- **Backend Rate Limit & Quota Diagnostics**:
  - Dedicated `View Quotas & Usage` command displaying real-time daily submissions, monthly allocations, and standard HTTP 429 Retry-After guidance.
  - Transparent error diagnostics for emergency billable operation shutoffs (HTTP 503).
- **Default Cloud Backend Connectivity**:
  - Configured by default to connect to the production Render cloud backend (`https://researchpilot-api-cb0c.onrender.com`), while remaining fully user-configurable via `researchpilot.backendUrl`.

