const { describe, it } = require("node:test");
const assert = require("node:assert");
const Module = require("module");

// Provide mock 'vscode' module when running in standalone Node.js test environment
const originalLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === "vscode") {
    return {
      window: {
        createWebviewPanel: () => ({
          webview: { onDidReceiveMessage: () => {} },
          onDidDispose: () => {},
        }),
      },
      ViewColumn: { Active: 1 },
      env: { clipboard: { writeText: async () => {} } },
      commands: { executeCommand: async () => {} },
      workspace: { getConfiguration: () => ({ get: () => {} }) },
    };
  }
  return originalLoad.apply(this, arguments);
};

const { ReportPanel } = require("../src/views/reportPanel");
const { SidebarProvider } = require("../src/views/sidebarProvider");

describe("Webview Security & CSP Tests", () => {
  it("should enforce Content-Security-Policy in ReportPanel webview", () => {
    const mockContext = { extensionUri: { fsPath: "/tmp" } };
    const mockClient = {};
    const panel = new ReportPanel(mockContext, mockClient);

    const html = panel._getReportHtml({
      title: "Test Report",
      executive_summary: "Summary text",
      claims: [],
      references: [],
    }, "Test Query");

    assert.match(html, /<meta http-equiv="Content-Security-Policy"/);
    assert.match(html, /default-src 'none'/);
    assert.match(html, /style-src 'unsafe-inline'/);
    assert.match(html, /script-src 'unsafe-inline'/);
  });

  it("should sanitize and block malicious javascript: URLs in references", () => {
    const mockContext = { extensionUri: { fsPath: "/tmp" } };
    const mockClient = {};
    const panel = new ReportPanel(mockContext, mockClient);

    const maliciousReport = {
      title: "XSS Probe",
      executive_summary: "Summary",
      claims: [],
      references: [
        {
          citation_label: "[1]",
          title: "Malicious Source",
          url: "javascript:alert('XSS')",
        },
        {
          citation_label: "[2]",
          title: "Legitimate Source",
          url: "https://example.com/legit-paper",
        },
      ],
    };

    const html = panel._getReportHtml(maliciousReport, "Query");

    // javascript: URL must NEVER be rendered as an <a href="javascript:...">
    assert.doesNotMatch(html, /<a href="javascript:/);
    // Legitimate https: URL must be rendered safely with rel="noopener noreferrer"
    assert.match(html, /<a href="https:\/\/example\.com\/legit-paper" target="_blank" rel="noopener noreferrer">/);
  });

  it("should enforce Content-Security-Policy in SidebarProvider webview", () => {
    const mockContext = { extensionUri: { fsPath: "/tmp" } };
    const mockClient = {};
    const mockReportPanel = {};
    const sidebar = new SidebarProvider(mockContext, mockClient, mockReportPanel);

    const html = sidebar._getHtmlForWebview();
    assert.match(html, /<meta http-equiv="Content-Security-Policy"/);
    assert.match(html, /default-src 'none'/);
  });

  it("should escape special characters in _escapeHtml", () => {
    const mockContext = { extensionUri: { fsPath: "/tmp" } };
    const panel = new ReportPanel(mockContext, {});

    const escaped = panel._escapeHtml('<script>alert("XSS & \'attack\'")</script>');
    assert.strictEqual(
      escaped,
      '&lt;script&gt;alert(&quot;XSS &amp; &#039;attack&#039;&quot;)&lt;/script&gt;'
    );
  });
});
