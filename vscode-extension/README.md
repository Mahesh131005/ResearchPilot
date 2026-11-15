# ResearchPilot for VS Code

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://marketplace.visualstudio.com/items?itemName=ResearchPilot.researchpilot-vscode)
[![Visual Studio Marketplace](https://img.shields.io/badge/marketplace-ResearchPilot-green.svg)](https://marketplace.visualstudio.com/items?itemName=ResearchPilot.researchpilot-vscode)

Institutional-grade, multi-agent AI research, document RAG retrieval, and empirical fact-checking directly inside Visual Studio Code.

---

## 1. Product Overview

**ResearchPilot** connects your editor directly to an autonomous, multi-agent research pipeline designed to tackle complex technical, scientific, and empirical questions without leaving your code or workspace.

Unlike conventional conversational chatbots that hallucinate or rely on ungrounded pre-training memory, ResearchPilot decomposes your inquiry across specialized agents that plan sub-questions, gather external web evidence via Tavily, retrieve internal workspace PDF knowledge via pgvector semantic search, normalize cross-source findings, audit claims with a dedicated fact-checker, and synthesize rigorous, cited reports.

---

## 2. Key Features

- **Activity Bar & Dedicated Sidebar**:
  - Always-accessible research hub in your activity bar.
  - Submit research queries, monitor live milestone streams, and inspect past research history.
- **Multi-Agent Orchestration**:
  - Real-time execution telemetry streamed from 5 cooperative agents:
    1. **Planner Agent**: Decomposes high-level questions into granular investigation hypotheses.
    2. **Web Research Agent**: Queries live web sources using Tavily Search API.
    3. **Document Research Agent**: Performs semantic cosine similarity retrieval over ingested PDF embeddings.
    4. **Evidence Normalizer**: Reconciles dates, units, claim targets, and duplicate citations.
    5. **Fact Checker & Report Writer**: Cross-audits claims against source quotes and computes confidence scores.
- **Fact-Checked Claims Audit & Contradictions**:
  - Tabulated claim audits categorizing each assertion as `SUPPORTED`, `PARTIALLY_SUPPORTED`, `CONTRADICTORY`, or `UNSUPPORTED`.
  - Dedicated discrepancies section highlighting conflicting claims across academic or industry sources.
- **Context Menu "Research Selected Text"**:
  - Highlight any function, architectural block, or paragraph in any editor, right-click, and select **Research Selected Text** with explicit user confirmation.
- **Export to Workspace Markdown**:
  - Export completed research briefs, complete with citations, metadata, and verdict tables, directly to your workspace as structured `.md` files.
- **Secure Token Storage**:
  - Uses VS Code's OS-native `SecretStorage` keychain. JWT tokens and credentials are never written to plain-text settings, logs, or webview DOMs.
- **Quota & Spending Transparency**:
  - Direct feedback on tier limits, daily submissions, hourly ceilings, and HTTP 429 Retry-After timeframes.

---

## 3. Installation & Getting Started

### Installation
1. Open Visual Studio Code.
2. Open the Extensions view (`Ctrl+Shift+X` or `Cmd+Shift+X`).
3. Search for **ResearchPilot**.
4. Click **Install**.

### Quick Start
1. Click the **ResearchPilot** icon in the VS Code Activity Bar (left sidebar).
2. If you do not have an active session, click **Log In** in the sidebar.
3. Enter your account email and password.
4. Type your research inquiry into the query box (e.g., *"Compare zero-knowledge proofs vs. optimistic rollups for L2 scalability"*).
5. Select your desired depth (`Quick`, `Standard`, or `Deep`) and click **Launch Research**.
6. Follow the live agent stream as each milestone completes, then click **View Report** to open the rich report viewer.

---

## 4. Login Instructions & Authentication

ResearchPilot authenticates against your configured backend instance using standard JWT credentials:

1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P`) to open the Command Palette.
2. Run **`ResearchPilot: Log In to Platform`**.
3. Enter your registered email address (e.g., `admin@researchpilot.local` or your organization email).
4. Enter your account password.
5. Upon successful authentication, your access and refresh tokens are securely encrypted in VS Code `SecretStorage`.
6. To log out at any time, run **`ResearchPilot: Log Out`**.

Tokens are automatically rotated in the background when access tokens expire.

---

## 5. Research Workflow

```
   [ Editor / Selected Text / Sidebar Prompt ]
                       │
                       ▼
            [ 1. Planner Agent ]
         Decomposes inquiry & scope
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
[ 2. Web Agent (Tavily) ]  [ 3. Doc Agent (pgvector) ]
 Live external search       Internal document RAG
         │                           │
         └─────────────┬─────────────┘
                       ▼
         [ 4. Evidence Normalizer ]
           Aligns facts & metrics
                       │
                       ▼
          [ 5. Fact-Checker Agent ]
          Validates claim verdicts
                       │
                       ▼
       [ 6. Synthesized Report Viewer ]
         Interactive audit & Markdown export
```

---

## 6. Backend Connection Settings

The extension is pre-configured to connect directly to the official Render cloud API service. You can customize the backend target if hosting your own instance:

Open **Settings** (`Ctrl+,` or `Cmd+,`), search for `ResearchPilot`, or edit `settings.json`:

| Setting | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `researchpilot.backendUrl` | `string` | `https://researchpilot-api-cb0c.onrender.com` | FastAPI backend URL. Can be set to `http://localhost:8000` for local Docker setups. |
| `researchpilot.defaultDepth` | `enum` | `standard` | Default investigation depth (`quick`, `standard`, `deep`). |
| `researchpilot.enableWeb` | `boolean` | `true` | Enable live external web search via Tavily. |
| `researchpilot.enableDocuments` | `boolean` | `true` | Enable internal document semantic search via pgvector. |

---

## 7. Privacy & Selected-Text Consent

ResearchPilot is designed around strict developer privacy and zero silent transmission:

- **No Silent Telemetry**: The extension **never** scans, monitors, or uploads your workspace files or code in the background.
- **Explicit Confirmation for Selected Text**: When triggering **Research Selected Text** from the editor context menu, the extension displays a confirmation dialog previewing the selected characters before any network call is dispatched.
- **Credential Isolation**: No API keys (such as Google Gemini or Tavily keys) are ever distributed to or stored inside the extension client. All third-party provider calls execute exclusively on the authenticated backend.
- **Webview Isolation**: All webview panels enforce strict Content Security Policies (`default-src 'none'`), disallowing arbitrary remote script execution or external style injection.

---

## 8. Current Limitations & Free Tier Notice

- **Free-Tier Sleeping**: When connecting to a free Render deployment, the backend web service spins down after 15 minutes of inactivity. The initial request after sleeping may incur a cold-start delay of 50–90 seconds while the container boots.
- **In-Memory Job Lifecycle on Free Tier**: Because free cloud tiers cycle containers periodically, deep research tasks requiring extended runtimes should be initiated with `quick` or `standard` depth to complete within 2–4 minutes.
- **Ephemeral Uploaded Files**: On free container tiers without persistent disks, physical PDF binaries are cleared upon server restart, though text chunks and vector embeddings remain permanently queryable in PostgreSQL.

---

## 9. Available Commands

Access these commands at any time via the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`):

- **`ResearchPilot: Start New Research`**: Opens prompt to start a research job.
- **`ResearchPilot: Research Selected Text`**: Researches highlighted editor text with confirmation.
- **`ResearchPilot: Save Active Report as Markdown`**: Saves the currently viewed report as a `.md` document in the workspace.
- **`ResearchPilot: Log In to Platform`**: Prompts for credentials and logs into the backend.
- **`ResearchPilot: Log Out`**: Clears securely stored tokens.
- **`ResearchPilot: View Quotas & Usage`**: Displays current rate limits, monthly quotas, and tier allocations.
- **`ResearchPilot: Refresh Research History`**: Syncs recent research jobs in the sidebar.

---

## 10. Support & Feedback

- **Issues & Bug Reports**: [GitHub Issues](https://github.com/Mahesh131005/ResearchPilot/issues)
- **Documentation & Deployment**: See `docs/RENDER_FREE_DEPLOYMENT_GUIDE.md` in the project repository.
- **Platform Web Interface**: [ResearchPilot Web](https://researchpilot-web.onrender.com)
