# VS Code Extension Architecture — ResearchPilot

## 1. Overview & Architectural Goals

The **ResearchPilot VS Code Extension** (`researchpilot-vscode`) extends the ResearchPilot multi-user research platform directly into developer and analyst workflows within Visual Studio Code.

Rather than duplicating backend logic, the extension operates as an independent, lightweight client of the shared FastAPI backend. It enforces the same authentication standards, per-user rate limits, provider usage telemetry, and emergency billable guardrails as the browser SPA.

```mermaid
flowchart TD
    subgraph VSCode_Extension ["VS Code Extension Host (Node.js 22 / JavaScript)"]
        Sidebar["Sidebar Provider (WebviewView)"]
        ReportViewer["Report Viewer Panel (WebviewPanel)"]
        Cmds["Command Handlers (researchSelection, etc.)"]
        
        SecretStore[("VS Code SecretStorage")]
        TokenMgr["TokenManager"]
        ApiClient["ResearchPilotApiClient (Fetch)"]
        SSEStream["SSEResearchStream"]

        Sidebar <-->|postMessage (Zero Token Exposure)| TokenMgr
        Cmds --> ApiClient
        TokenMgr <--> SecretStore
        ApiClient --> TokenMgr
    end

    subgraph Backend_Platform ["Shared FastAPI Backend (Port 8000)"]
        AuthRouter["POST /api/v1/auth/login, refresh"]
        JobRouter["POST /api/v1/research/jobs"]
        SSEEndpoint["GET /api/v1/research/jobs/{id}/stream"]
        ReportEndpoint["GET /api/v1/research/jobs/{id}/report"]
        UsageEndpoint["GET /api/v1/usage/me"]

        LangGraphEngine["5-Agent LangGraph Research Engine"]
        PostgresDB[("PostgreSQL 16 + pgvector")]
    end

    ApiClient -->|Bearer JWT HS256| AuthRouter
    ApiClient -->|Bearer JWT HS256| JobRouter
    ApiClient -->|Bearer JWT HS256| ReportEndpoint
    ApiClient -->|Bearer JWT HS256| UsageEndpoint
    SSEStream -->|text/event-stream| SSEEndpoint

    JobRouter --> LangGraphEngine
    LangGraphEngine --> PostgresDB
```

---

## 2. Directory Structure

```
vscode-extension/
├── package.json               # Extension manifest, contributes activitybar, views, commands, settings
├── extension.js               # Main entrypoint activating commands and providers
├── media/
│   └── icon.svg               # Extension activity bar icon
├── src/
│   ├── api/
│   │   ├── client.js          # REST client with automatic 401 token refresh & error formatting
│   │   └── sse.js             # Chunked SSE event stream parser
│   ├── auth/
│   │   └── tokenManager.js    # VS Code SecretStorage wrapper for secure token management
│   ├── commands/
│   │   ├── authCommands.js    # login, logout, viewUsage, refreshHistory
│   │   └── researchCommands.js# researchSelection, startResearch, saveReportMarkdown
│   ├── utils/
│   │   ├── errorFormatter.js  # HTTP 429, 503, 401, 404, 422 formatter
│   │   └── markdownExporter.js# Publication-grade Markdown serializer
│   └── views/
│       ├── reportPanel.js     # Full editor tab webview with interactive claims & citations
│       └── sidebarProvider.js # Primary sidebar provider with login, meters, stepper, history
└── test/
    ├── client.test.js         # API client & error handling tests
    ├── errorFormatter.test.js # Error diagnostic tests
    ├── markdownExporter.test.js# Markdown serialization tests
    ├── sse.test.js            # SSE stream parser tests
    └── tokenManager.test.js   # SecretStorage token persistence tests
```

---

## 3. Security & Token Isolation Invariants

1. **Zero Webview Token Exposure**:
   - Access tokens and refresh tokens are stored exclusively in VS Code's native `SecretStorage` (`context.secrets`) on the developer's local OS keychain.
   - Webviews communicate with the extension host using asynchronous `acquireVsCodeApi().postMessage()` messaging.
   - Tokens are **never** passed into Webview HTML, script tags, local storage, or webview message payloads.
2. **Explicit User Consent for Selection Research**:
   - The `researchpilot.researchSelection` command inspects the highlighted text and displays an explicit modal confirmation dialog disclosing the snippet before dispatching it to the backend.
   - No automatic full-workspace indexing or background file scanning occurs.
3. **Automatic Refresh Token Rotation**:
   - Upon encountering an expired access token (`HTTP 401`), `ResearchPilotApiClient` intercepts the failure and executes `POST /api/v1/auth/refresh` using the securely stored refresh token.
   - The newly rotated token pair is persisted back to `SecretStorage` and the failed request is re-executed seamlessly.
4. **Backend-Enforced Rate Limits & Quotas**:
   - The extension does not perform client-side quota counting. All rate limits (hourly submissions, daily jobs, monthly quotas, concurrent job locks) are enforced by the FastAPI backend.
   - Rejections (`HTTP 429`) parse the `Retry-After` header and structured error payload, rendering informative recovery timers.
5. **Emergency Policy Switch Interception**:
   - When the backend's `BILLABLE_OPERATIONS_ENABLED` is turned off, the extension catches `HTTP 503` and clearly informs the user that live billable research has been temporarily paused by policy while past reports remain accessible.

---

## 4. Extension Commands Reference

| Command | Identifier | UI Access | Description |
| :--- | :--- | :--- | :--- |
| **Start New Research** | `researchpilot.startResearch` | Command Palette | Launches an interactive query input box and depth selector. |
| **Research Selected Text** | `researchpilot.researchSelection` | Editor Context Menu | Researches highlighted code or prose with explicit confirmation. |
| **Save Report as Markdown** | `researchpilot.saveReportMarkdown` | Command Palette / Report Viewer | Exports the active analytical report as a `.md` file to the workspace. |
| **Log In to Platform** | `researchpilot.login` | Command Palette / Sidebar | Authenticates user against backend and saves tokens to SecretStorage. |
| **Log Out** | `researchpilot.logout` | Command Palette / Sidebar | Clears tokens from SecretStorage. |
| **View Quotas & Usage** | `researchpilot.viewUsage` | Command Palette / Sidebar Title | Displays real-time daily/monthly quota consumption and token usage. |
| **Refresh History** | `researchpilot.refreshHistory` | Sidebar Title Bar | Reloads the research history list from the backend. |

---

## 5. Automated Verification

The extension includes 16 automated tests executed via `node:test`:

```bash
cd vscode-extension
npm test
```

Verification covers:
- Normalized URL construction and health checks.
- Credential authentication and `SecretStorage` token persistence.
- HTTP 429 quota exhaustion and Retry-After formatting.
- HTTP 503 emergency billable shutoff handling.
- HTTP 401 refresh token rotation retry.
- Chunked Server-Sent Events stream parsing and event dispatch.
- Multi-section report Markdown serialization.

