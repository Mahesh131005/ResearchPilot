# ResearchPilot for VS Code

Institutional-grade, multi-agent AI research, RAG retrieval, and empirical fact-checking directly inside Visual Studio Code.

---

## Features

- **Activity Bar & Dedicated Sidebar**: Research inquiries, real-time agent progression, and research history.
- **Multi-Agent Orchestration**: Transparent execution stream across Planner, Web Research (Tavily), Document Research (pgvector RAG), Evidence Normalizer, Fact Checker, and Report Writer.
- **Secure Token Storage**: Authenticates using VS Code native `SecretStorage`. Credentials and JWT tokens are never exposed to webviews.
- **Research Selected Text**: Highlight code or text in any editor, right-click, and select **Research Selected Text** with explicit confirmation.
- **Fact-Checked Claims Audit**: Tabulated claim verification status (`SUPPORTED`, `PARTIALLY_SUPPORTED`, `CONTRADICTORY`, `UNSUPPORTED`), confidence metrics, and evidence quotes.
- **Contradictory Findings Section**: Highlights empirical discrepancies detected across sources.
- **Export as Markdown**: Save any generated research report directly to your active workspace with a single click.
- **Backend Rate Limit & Quota Transparency**: Live feedback on daily jobs, monthly allocations, and standard HTTP 429 Retry-After telemetry.

---

## Extension Settings

This extension contributes the following settings:

* `researchpilot.backendUrl`: URL of the ResearchPilot FastAPI backend (default: `http://localhost:8000`).
* `researchpilot.defaultDepth`: Default research depth (`quick`, `standard`, `deep`).
* `researchpilot.enableWeb`: Enable live external web research via Tavily (default: `true`).
* `researchpilot.enableDocuments`: Enable internal document RAG retrieval over uploaded PDFs (default: `true`).

---

## Commands

- `ResearchPilot: Start New Research`: Launch an interactive research inquiry.
- `ResearchPilot: Research Selected Text`: Submit selected editor text for multi-agent synthesis.
- `ResearchPilot: Save Active Report as Markdown`: Export the current report to `.md`.
- `ResearchPilot: Log In to Platform`: Authenticate with user credentials.
- `ResearchPilot: Log Out`: Revoke and clear local authentication tokens.
- `ResearchPilot: View Quotas & Usage`: Inspect current rate limit and token consumption metrics.
- `ResearchPilot: Refresh Research History`: Fetch recent jobs from the backend.

---

## Running Automated Tests

```bash
cd vscode-extension
npm test
```

