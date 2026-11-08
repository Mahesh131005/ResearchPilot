/**
 * SidebarProvider
 * Implements vscode.WebviewViewProvider for the ResearchPilot sidebar.
 * Enables login, live research submissions, real-time SSE progress streaming,
 * quota meters, and research history review.
 */

const vscode = require("vscode");
const { SSEResearchStream } = require("../api/sse");

class SidebarProvider {
  /**
   * @param {vscode.ExtensionContext} context
   * @param {import('../api/client').ResearchPilotApiClient} apiClient
   * @param {import('../views/reportPanel').ReportPanel} reportPanel
   */
  constructor(context, apiClient, reportPanel) {
    this.context = context;
    this.apiClient = apiClient;
    this.reportPanel = reportPanel;
    this.view = null;
    this.activeStream = null;
  }

  resolveWebviewView(webviewView) {
    this.view = webviewView;
    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this.context.extensionUri],
    };

    webviewView.webview.html = this._getHtmlForWebview();

    webviewView.webview.onDidReceiveMessage(async (data) => {
      switch (data.command) {
        case "init":
          await this.syncState();
          break;
        case "login":
          await this.handleLogin(data.email, data.password);
          break;
        case "register":
          await this.handleRegister(data.email, data.password, data.fullName);
          break;
        case "logout":
          await this.handleLogout();
          break;
        case "startResearch":
          await this.handleStartResearch(data);
          break;
        case "viewReport":
          await this.reportPanel.show(data.jobId, data.query);
          break;
        case "refresh":
          await this.syncState();
          break;
      }
    });

    this.syncState();
  }

  async syncState() {
    if (!this.view) return;

    // Check backend health
    const health = await this.apiClient.checkHealth();
    const isAuth = await this.apiClient.tokenManager.isAuthenticated();
    const userInfo = await this.apiClient.tokenManager.getUserInfo();

    let usage = null;
    let history = [];
    let docs = [];

    if (isAuth) {
      try {
        usage = await this.apiClient.getUsage();
      } catch {}
      try {
        history = await this.apiClient.listJobs();
      } catch {}
      try {
        docs = await this.apiClient.getDocuments();
      } catch {}
    }

    this.view.webview.postMessage({
      type: "stateSync",
      data: {
        connected: health.ok,
        backendStatus: health.status || health.error,
        authenticated: isAuth,
        user: userInfo,
        usage,
        history: history.slice(0, 15),
        documents: docs,
      },
    });
  }

  async handleLogin(email, password) {
    const res = await this.apiClient.login(email, password);
    if (!res.success) {
      vscode.window.showErrorMessage(`ResearchPilot: ${res.error}`);
      this.view?.webview.postMessage({ type: "authError", message: res.error });
      return;
    }
    vscode.window.showInformationMessage(`ResearchPilot: Logged in as ${res.user.email}`);
    await this.syncState();
  }

  async handleRegister(email, password, fullName) {
    const res = await this.apiClient.register(email, password, fullName);
    if (!res.success) {
      vscode.window.showErrorMessage(`ResearchPilot: ${res.error}`);
      this.view?.webview.postMessage({ type: "authError", message: res.error });
      return;
    }
    vscode.window.showInformationMessage(`ResearchPilot: Registered and logged in as ${res.user.email}`);
    await this.syncState();
  }

  async handleLogout() {
    await this.apiClient.tokenManager.clearTokens();
    vscode.window.showInformationMessage("ResearchPilot: Logged out.");
    await this.syncState();
  }

  async handleStartResearch(payload) {
    const { query, depth, enableWeb, enableDocuments, documentIds } = payload;
    if (!query || query.trim().length < 5) {
      vscode.window.showWarningMessage("Research query must be at least 5 characters long.");
      return;
    }

    this.view?.webview.postMessage({ type: "researchStarted", query });

    const submission = await this.apiClient.createJob({
      query: query.trim(),
      depth: depth || "standard",
      enableWeb: enableWeb !== false,
      enableDocuments: enableDocuments !== false,
      documentIds: documentIds || [],
    });

    if (!submission.success) {
      vscode.window.showErrorMessage(`Research Failed: ${submission.error}`);
      this.view?.webview.postMessage({ type: "researchError", message: submission.error });
      return;
    }

    const job = submission.job;
    vscode.window.showInformationMessage(`Research Started: Job ${job.id.slice(0, 8)}...`);

    // Stream SSE progress
    const token = await this.apiClient.tokenManager.getAccessToken();
    const streamUrl = this.apiClient.url(`api/v1/research/jobs/${job.id}/stream`);

    if (this.activeStream) {
      this.activeStream.abort();
    }

    this.activeStream = new SSEResearchStream(streamUrl, token, {
      onEvent: (event) => {
        this.view?.webview.postMessage({
          type: "streamEvent",
          data: event,
        });
      },
      onComplete: async () => {
        this.view?.webview.postMessage({
          type: "researchCompleted",
          jobId: job.id,
          query,
        });
        vscode.window.showInformationMessage(`Research Completed: "${query.slice(0, 40)}"`, "View Report").then(selection => {
          if (selection === "View Report") {
            this.reportPanel.show(job.id, query);
          }
        });
        await this.syncState();
      },
      onError: (err) => {
        this.view?.webview.postMessage({
          type: "researchError",
          message: err.message,
        });
      },
    });

    this.activeStream.start();
  }

  _getHtmlForWebview() {
    return `<!DOCTYPE html>
    <html lang="en">
      <head>
        <meta charset="UTF-8">
        <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
          body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            color: var(--vscode-foreground);
            background: var(--vscode-sideBar-background);
            padding: 12px;
            margin: 0;
            box-sizing: border-box;
          }
          .card {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--vscode-widget-border);
            border-radius: 6px;
            padding: 12px;
            margin-bottom: 12px;
          }
          .title { font-weight: 600; font-size: 13px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
          .status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 6px; }
          .dot-green { background: #22c55e; }
          .dot-red { background: #ef4444; }
          input, select, textarea {
            width: 100%;
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            border: 1px solid var(--vscode-input-border);
            border-radius: 4px;
            padding: 6px 8px;
            font-family: inherit;
            font-size: inherit;
            box-sizing: border-box;
            margin-bottom: 8px;
          }
          input:focus, textarea:focus, select:focus {
            outline: 1px solid var(--vscode-focusBorder);
          }
          button {
            width: 100%;
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 500;
            margin-bottom: 6px;
          }
          button:hover { background: var(--vscode-button-hoverBackground); }
          .btn-secondary {
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
          }
          .btn-secondary:hover { background: var(--vscode-button-secondaryHoverBackground); }
          .row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
          .row label { font-size: 11px; display: flex; align-items: center; gap: 4px; cursor: pointer; }
          .stepper { margin-top: 8px; border-left: 2px solid var(--vscode-widget-border); padding-left: 10px; }
          .step-item { margin-bottom: 6px; font-size: 11px; }
          .step-agent { font-weight: 600; color: #60a5fa; }
          .step-time { font-size: 9px; opacity: 0.6; }
          .history-item {
            padding: 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            font-size: 11px;
            cursor: pointer;
            border-radius: 4px;
          }
          .history-item:hover { background: rgba(255, 255, 255, 0.06); }
          .badge { font-size: 9px; padding: 2px 6px; border-radius: 8px; text-transform: uppercase; font-weight: 600; }
          .badge-completed { background: rgba(34, 197, 94, 0.2); color: #4ade80; }
          .badge-processing { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
          .badge-failed { background: rgba(239, 68, 68, 0.2); color: #f87171; }
          .badge-queued { background: rgba(234, 179, 8, 0.2); color: #facc15; }
          .hidden { display: none; }
          .meter { height: 6px; background: rgba(255, 255, 255, 0.1); border-radius: 3px; overflow: hidden; margin-top: 4px; }
          .meter-bar { height: 100%; background: #3b82f6; width: 0%; transition: width 0.3s; }
        </style>
      </head>
      <body>
        <!-- Header & Connection -->
        <div class="card" style="padding: 8px 12px;">
          <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px;">
            <div>
              <span id="conn-dot" class="status-dot dot-red"></span>
              <span id="conn-text">Connecting...</span>
            </div>
            <button class="btn-secondary" style="width: auto; padding: 2px 8px; margin: 0; font-size: 10px;" onclick="syncState()">Refresh</button>
          </div>
        </div>

        <!-- Auth Section -->
        <div id="auth-card" class="card">
          <div class="title">
            <span id="auth-title">Log In to ResearchPilot</span>
          </div>
          <div id="login-fields">
            <input type="email" id="email" placeholder="Email address" />
            <input type="password" id="password" placeholder="Password" />
            <div id="register-name-field" class="hidden">
              <input type="text" id="fullname" placeholder="Full Name" />
            </div>
            <button id="btn-auth" onclick="submitAuth()">Log In</button>
            <button class="btn-secondary" id="btn-toggle-auth" onclick="toggleAuthMode()">Create an Account</button>
          </div>
          <div id="user-info" class="hidden">
            <div style="font-size: 11px; margin-bottom: 6px;">
              Logged in as: <strong id="user-email"></strong>
            </div>
            <!-- Quick Quota Preview -->
            <div id="quota-preview" style="font-size: 10px; margin-bottom: 8px; opacity: 0.9;">
              <div>Daily Jobs: <span id="quota-daily-text">0/10</span></div>
              <div class="meter"><div id="quota-daily-bar" class="meter-bar"></div></div>
            </div>
            <button class="btn-secondary" style="font-size: 11px; padding: 4px;" onclick="logout()">Log Out</button>
          </div>
        </div>

        <!-- Research Submission Card -->
        <div id="research-card" class="card hidden">
          <div class="title">New Research Inquiry</div>
          <textarea id="query-input" rows="3" placeholder="Enter complex research question (e.g. 'Compare MA-ALNS vs standard ALNS in link routing optimization')..."></textarea>
          
          <div class="row">
            <select id="depth-select" style="margin-bottom: 0;">
              <option value="quick">Quick (Overview)</option>
              <option value="standard" selected>Standard (In-Depth)</option>
              <option value="deep">Deep (Comprehensive)</option>
            </select>
          </div>

          <div class="row" style="justify-content: space-between;">
            <label><input type="checkbox" id="check-web" checked /> Web (Tavily)</label>
            <label><input type="checkbox" id="check-docs" checked /> Document RAG</label>
          </div>

          <button id="btn-submit" onclick="submitResearch()">Run Multi-Agent Research</button>

          <!-- Live Progress Stream -->
          <div id="live-progress" class="hidden" style="margin-top: 10px;">
            <div style="font-size: 11px; font-weight: 600; margin-bottom: 4px;">Live Multi-Agent Execution:</div>
            <div class="stepper" id="events-stream"></div>
          </div>
        </div>

        <!-- Research History -->
        <div id="history-card" class="card hidden">
          <div class="title">Recent Research Jobs</div>
          <div id="history-list"></div>
        </div>

        <script>
          const vscode = acquireVsCodeApi();
          let isRegisterMode = false;
          let isAuthenticated = false;

          function syncState() {
            vscode.postMessage({ command: 'init' });
          }

          function toggleAuthMode() {
            isRegisterMode = !isRegisterMode;
            document.getElementById('auth-title').innerText = isRegisterMode ? 'Register New Account' : 'Log In to ResearchPilot';
            document.getElementById('btn-auth').innerText = isRegisterMode ? 'Register' : 'Log In';
            document.getElementById('btn-toggle-auth').innerText = isRegisterMode ? 'Have an account? Log In' : 'Create an Account';
            document.getElementById('register-name-field').classList.toggle('hidden', !isRegisterMode);
          }

          function submitAuth() {
            const email = document.getElementById('email').value.trim();
            const password = document.getElementById('password').value;
            if (isRegisterMode) {
              const fullName = document.getElementById('fullname').value.trim();
              vscode.postMessage({ command: 'register', email, password, fullName });
            } else {
              vscode.postMessage({ command: 'login', email, password });
            }
          }

          function logout() {
            vscode.postMessage({ command: 'logout' });
          }

          function submitResearch() {
            const query = document.getElementById('query-input').value.trim();
            const depth = document.getElementById('depth-select').value;
            const enableWeb = document.getElementById('check-web').checked;
            const enableDocuments = document.getElementById('check-docs').checked;

            vscode.postMessage({
              command: 'startResearch',
              query,
              depth,
              enableWeb,
              enableDocuments
            });
          }

          function viewReport(jobId, query) {
            vscode.postMessage({ command: 'viewReport', jobId, query });
          }

          window.addEventListener('message', event => {
            const msg = event.data;
            switch (msg.type) {
              case 'stateSync':
                handleStateSync(msg.data);
                break;
              case 'researchStarted':
                document.getElementById('live-progress').classList.remove('hidden');
                document.getElementById('events-stream').innerHTML = '<div class="step-item">Initializing LangGraph agents...</div>';
                document.getElementById('btn-submit').disabled = true;
                document.getElementById('btn-submit').innerText = 'Research in Progress...';
                break;
              case 'streamEvent':
                appendStreamEvent(msg.data);
                break;
              case 'researchCompleted':
                document.getElementById('btn-submit').disabled = false;
                document.getElementById('btn-submit').innerText = 'Run Multi-Agent Research';
                break;
              case 'researchError':
                document.getElementById('btn-submit').disabled = false;
                document.getElementById('btn-submit').innerText = 'Run Multi-Agent Research';
                break;
            }
          });

          function handleStateSync(data) {
            // Connection
            const dot = document.getElementById('conn-dot');
            const txt = document.getElementById('conn-text');
            if (data.connected) {
              dot.className = 'status-dot dot-green';
              txt.innerText = 'Connected (v1)';
            } else {
              dot.className = 'status-dot dot-red';
              txt.innerText = data.backendStatus || 'Offline';
            }

            // Auth State
            isAuthenticated = data.authenticated;
            document.getElementById('login-fields').classList.toggle('hidden', isAuthenticated);
            document.getElementById('user-info').classList.toggle('hidden', !isAuthenticated);
            document.getElementById('research-card').classList.toggle('hidden', !isAuthenticated);
            document.getElementById('history-card').classList.toggle('hidden', !isAuthenticated);

            if (isAuthenticated && data.user) {
              document.getElementById('user-email').innerText = data.user.email;
              document.getElementById('auth-title').innerText = 'Account & Quotas';
            }

            // Usage meter
            if (data.usage && data.usage.limits) {
              const dailyUsed = data.usage.daily_jobs_used || 0;
              const dailyLimit = data.usage.limits.daily_jobs_limit || 10;
              document.getElementById('quota-daily-text').innerText = dailyUsed + ' / ' + dailyLimit;
              const pct = Math.min(100, Math.round((dailyUsed / dailyLimit) * 100));
              document.getElementById('quota-daily-bar').style.width = pct + '%';
            }

            // History
            if (data.history && data.history.length > 0) {
              const html = data.history.map(job => {
                const statusClass = 'badge badge-' + (job.status || 'queued');
                const title = (job.query || 'Research Inquiry').slice(0, 50);
                return '<div class="history-item" onclick="viewReport(\\'' + job.id + '\\', \\'' + encodeURIComponent(job.query || '') + '\\')">' +
                  '<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2px;">' +
                    '<span class="' + statusClass + '">' + job.status + '</span>' +
                    '<span style="font-size:9px; opacity:0.6;">' + (job.depth || 'standard') + '</span>' +
                  '</div>' +
                  '<div style="font-weight:500;">' + title + '...</div>' +
                '</div>';
              }).join('');
              document.getElementById('history-list').innerHTML = html;
            } else {
              document.getElementById('history-list').innerHTML = '<div style="font-size:11px; opacity:0.7;">No prior research jobs found.</div>';
            }
          }

          function escapeHtml(str) {
            const div = document.createElement('div');
            div.textContent = str || '';
            return div.innerHTML;
          }

          function appendStreamEvent(ev) {
            const container = document.getElementById('events-stream');
            const agent = ev.agent_name || 'Agent';
            const msg = ev.message || '';
            const div = document.createElement('div');
            div.className = 'step-item';
            div.innerHTML = '<span class="step-agent">' + escapeHtml(agent) + ':</span> ' + escapeHtml(msg);
            container.appendChild(div);
            container.scrollTop = container.scrollHeight;
          }

          // Initial sync
          vscode.postMessage({ command: 'init' });
        </script>
      </body>
    </html>`;
  }
}

module.exports = { SidebarProvider };

