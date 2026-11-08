/**
 * ReportPanel
 * Displays a full-screen institutional research report in a VS Code Webview panel.
 * Includes executive summary, key findings, fact-checked claims audit, contradictory findings,
 * verified citations, and one-click Markdown export.
 */

const vscode = require("vscode");
const { formatReportAsMarkdown } = require("../utils/markdownExporter");

class ReportPanel {
  /**
   * @param {vscode.ExtensionContext} context
   * @param {import('../api/client').ResearchPilotApiClient} apiClient
   */
  constructor(context, apiClient) {
    this.context = context;
    this.apiClient = apiClient;
    this.currentPanel = null;
    this.currentReport = null;
    this.currentQuery = "";
  }

  /**
   * Shows or updates the report panel with the report for a specific job.
   * @param {string} jobId
   * @param {string} [query=""]
   */
  async show(jobId, query = "") {
    this.currentQuery = query;

    if (this.currentPanel) {
      this.currentPanel.reveal(vscode.ViewColumn.Active);
    } else {
      this.currentPanel = vscode.window.createWebviewPanel(
        "researchpilot.reportViewer",
        "Research Report",
        vscode.ViewColumn.Active,
        {
          enableScripts: true,
          retainContextWhenHidden: true,
        }
      );

      this.currentPanel.onDidDispose(() => {
        this.currentPanel = null;
        this.currentReport = null;
      });

      this.currentPanel.webview.onDidReceiveMessage(async (message) => {
        switch (message.command) {
          case "saveMarkdown":
            await this.saveMarkdown();
            break;
          case "copyMarkdown":
            if (this.currentReport) {
              const md = formatReportAsMarkdown(this.currentReport, this.currentQuery);
              await vscode.env.clipboard.writeText(md);
              vscode.window.showInformationMessage("Research report copied to clipboard as Markdown.");
            }
            break;
        }
      });
    }

    this.currentPanel.webview.html = this._getLoadingHtml();

    try {
      const report = await this.apiClient.getReport(jobId);
      this.currentReport = report;
      this.currentPanel.title = report.title || "Research Report";
      this.currentPanel.webview.html = this._getReportHtml(report, query);
    } catch (err) {
      this.currentPanel.webview.html = this._getErrorHtml(err.message);
    }
  }

  async saveMarkdown() {
    if (!this.currentReport) return;
    const md = formatReportAsMarkdown(this.currentReport, this.currentQuery);

    const workspaceFolders = vscode.workspace.workspaceFolders;
    let defaultUri;
    const titleSlug = (this.currentReport.title || "ResearchReport")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .slice(0, 40);

    if (workspaceFolders && workspaceFolders.length > 0) {
      defaultUri = vscode.Uri.joinPath(workspaceFolders[0].uri, `${titleSlug}.md`);
    }

    const uri = await vscode.window.showSaveDialog({
      defaultUri,
      filters: { "Markdown Files": ["md"] },
    });

    if (uri) {
      await vscode.workspace.fs.writeFile(uri, Buffer.from(md, "utf-8"));
      const doc = await vscode.workspace.openTextDocument(uri);
      await vscode.window.showTextDocument(doc);
      vscode.window.showInformationMessage(`Report saved to ${uri.fsPath}`);
    }
  }

  _getLoadingHtml() {
    return `<!DOCTYPE html>
    <html>
      <head>
        <meta charset="UTF-8">
        <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline';">
        <style>
          body { font-family: var(--vscode-font-family); padding: 24px; color: var(--vscode-foreground); display: flex; align-items: center; justify-content: center; height: 80vh; }
          .spinner { border: 4px solid rgba(255, 255, 255, 0.1); width: 36px; height: 36px; border-radius: 50%; border-left-color: var(--vscode-button-background); animation: spin 1s linear infinite; }
          @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        </style>
      </head>
      <body>
        <div style="text-align: center;">
          <div class="spinner" style="margin: 0 auto 16px;"></div>
          <div>Loading institutional research report...</div>
        </div>
      </body>
    </html>`;
  }

  _getErrorHtml(errorMsg) {
    return `<!DOCTYPE html>
    <html>
      <head>
        <meta charset="UTF-8">
        <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline';">
        <style>
          body { font-family: var(--vscode-font-family); padding: 24px; color: var(--vscode-foreground); }
          .error-box { background: var(--vscode-inputValidation-errorBackground); border: 1px solid var(--vscode-inputValidation-errorBorder); padding: 16px; border-radius: 6px; }
        </style>
      </head>
      <body>
        <div class="error-box">
          <h3>Failed to Load Report</h3>
          <p>${this._escapeHtml(errorMsg)}</p>
        </div>
      </body>
    </html>`;
  }

  _getReportHtml(report, query) {
    const claims = Array.isArray(report.claims) ? report.claims : [];
    const references = Array.isArray(report.references) ? report.references : [];
    const keyFindings = Array.isArray(report.key_findings) ? report.key_findings : [];
    const contradictory = Array.isArray(report.contradictory_findings) ? report.contradictory_findings : [];
    const opportunities = Array.isArray(report.opportunities) ? report.opportunities : [];
    const risks = Array.isArray(report.risks_and_challenges) ? report.risks_and_challenges : [];

    const claimsRows = claims.map(c => {
      const status = (c.verification_status || "UNKNOWN").toLowerCase();
      const statusClass = status === "supported" ? "badge-supported" : status === "contradictory" ? "badge-contradictory" : "badge-warning";
      const conf = c.confidence_score !== undefined ? `${Math.round(c.confidence_score * 100)}%` : "N/A";
      return `<tr>
        <td><strong>${this._escapeHtml(c.claim_text)}</strong></td>
        <td><span class="badge ${statusClass}">${status.toUpperCase()}</span></td>
        <td>${conf}</td>
        <td><em>"${this._escapeHtml(c.evidence_quote || 'N/A')}"</em></td>
        <td>${this._escapeHtml(c.citation_source || 'N/A')}</td>
      </tr>`;
    }).join("");

    const refItems = references.map((r, idx) => {
      const label = r.citation_label || `[${idx + 1}]`;
      const pageInfo = r.page_number ? ` (Page ${r.page_number})` : "";
      let link = "";
      if (r.url) {
        const rawUrl = String(r.url).trim();
        if (rawUrl.startsWith("http://") || rawUrl.startsWith("https://")) {
          link = `<a href="${this._escapeHtml(rawUrl)}" target="_blank" rel="noopener noreferrer">${this._escapeHtml(rawUrl)}</a>`;
        } else {
          link = `<span>${this._escapeHtml(rawUrl)}</span>`;
        }
      }
      return `<li style="margin-bottom: 8px;">
        <strong>${this._escapeHtml(label)} ${this._escapeHtml(r.title)}</strong>${pageInfo} ${link}
        ${r.snippet ? `<div style="font-size: 0.9em; opacity: 0.8; margin-top: 2px;">"${this._escapeHtml(r.snippet)}"</div>` : ""}
      </li>`;
    }).join("");

    return `<!DOCTYPE html>
    <html lang="en">
      <head>
        <meta charset="UTF-8">
        <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src https: data:;">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
          body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            color: var(--vscode-foreground);
            background: var(--vscode-editor-background);
            line-height: 1.6;
            padding: 24px 36px;
            max-width: 960px;
            margin: 0 auto;
          }
          h1, h2, h3 { color: var(--vscode-foreground); font-weight: 600; }
          h1 { border-bottom: 1px solid var(--vscode-widget-border); padding-bottom: 8px; margin-top: 0; }
          h2 { margin-top: 28px; border-bottom: 1px solid rgba(255, 255, 255, 0.08); padding-bottom: 4px; }
          .header-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
          .actions { display: flex; gap: 8px; }
          button {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            border: none;
            padding: 6px 14px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
          }
          button:hover { background: var(--vscode-button-hoverBackground); }
          .btn-secondary {
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
          }
          .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
          }
          .badge-supported { background: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.3); }
          .badge-contradictory { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
          .badge-warning { background: rgba(234, 179, 8, 0.2); color: #facc15; border: 1px solid rgba(234, 179, 8, 0.3); }
          .callout-warning {
            background: rgba(239, 68, 68, 0.1);
            border-left: 4px solid #ef4444;
            padding: 12px 16px;
            border-radius: 0 4px 4px 0;
            margin: 16px 0;
          }
          table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 12px; }
          th, td { text-align: left; padding: 10px; border-bottom: 1px solid var(--vscode-widget-border); }
          th { background: rgba(255, 255, 255, 0.04); font-weight: 600; }
          .meta-pill { background: rgba(255, 255, 255, 0.08); padding: 4px 10px; border-radius: 12px; font-size: 12px; }
        </style>
      </head>
      <body>
        <div class="header-bar">
          <div>
            <span class="meta-pill">ResearchPilot Multi-Agent Synthesis</span>
            ${query ? `<span class="meta-pill" style="margin-left: 8px;">Query: "${this._escapeHtml(query)}"</span>` : ""}
          </div>
          <div class="actions">
            <button onclick="saveMarkdown()">Save as Markdown (.md)</button>
            <button class="btn-secondary" onclick="copyMarkdown()">Copy Markdown</button>
          </div>
        </div>

        <h1>${this._escapeHtml(report.title || "Research Report")}</h1>

        <h2>Executive Summary</h2>
        <p>${this._escapeHtml(report.executive_summary || "No executive summary provided.")}</p>

        ${report.industry_overview ? `<h2>Industry Context</h2><p>${this._escapeHtml(report.industry_overview)}</p>` : ""}

        <h2>Key Research Discoveries</h2>
        <ol>
          ${keyFindings.map(f => `<li>${this._escapeHtml(f)}</li>`).join("")}
        </ol>

        ${contradictory.length > 0 ? `
          <h2>Contradictory Findings & Discrepancies</h2>
          <div class="callout-warning">
            <strong>Critical Discrepancy Alert:</strong> The multi-agent fact check detected opposing empirical assertions across sources:
            <ul style="margin: 8px 0 0 16px;">
              ${contradictory.map(cf => `<li>${this._escapeHtml(cf)}</li>`).join("")}
            </ul>
          </div>
        ` : ""}

        <h2>Fact-Checked Claims Audit</h2>
        <table>
          <thead>
            <tr>
              <th>Factual Assertion</th>
              <th>Status</th>
              <th>Confidence</th>
              <th>Evidence Quote</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            ${claimsRows || '<tr><td colspan="5">No discrete claims audited.</td></tr>'}
          </tbody>
        </table>

        ${opportunities.length > 0 ? `
          <h2>Strategic Opportunities</h2>
          <ul>${opportunities.map(o => `<li>${this._escapeHtml(o)}</li>`).join("")}</ul>
        ` : ""}

        ${risks.length > 0 ? `
          <h2>Risks & Challenges</h2>
          <ul>${risks.map(r => `<li>${this._escapeHtml(r)}</li>`).join("")}</ul>
        ` : ""}

        ${report.future_outlook ? `<h2>Future Outlook (3-5 Years)</h2><p>${this._escapeHtml(report.future_outlook)}</p>` : ""}

        <h2>Verified References & Provenance</h2>
        <ul style="padding-left: 20px;">
          ${refItems || '<li>No references recorded.</li>'}
        </ul>

        <script>
          const vscode = acquireVsCodeApi();
          function saveMarkdown() {
            vscode.postMessage({ command: 'saveMarkdown' });
          }
          function copyMarkdown() {
            vscode.postMessage({ command: 'copyMarkdown' });
          }
        </script>
      </body>
    </html>`;
  }

  _escapeHtml(text) {
    if (!text) return "";
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
}

module.exports = { ReportPanel };

