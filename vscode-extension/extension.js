/**
 * ResearchPilot VS Code Extension
 * Main Entry Point
 */

const vscode = require("vscode");
const { TokenManager } = require("./src/auth/tokenManager");
const { ResearchPilotApiClient } = require("./src/api/client");
const { ReportPanel } = require("./src/views/reportPanel");
const { SidebarProvider } = require("./src/views/sidebarProvider");
const { registerResearchCommands } = require("./src/commands/researchCommands");
const { registerAuthCommands } = require("./src/commands/authCommands");

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
  console.log("Activating ResearchPilot VS Code extension...");

  // 1. Initialize Token Storage
  const tokenManager = new TokenManager(context.secrets);

  // 2. Initialize API Client
  const getBackendUrl = () => {
    const config = vscode.workspace.getConfiguration("researchpilot");
    return config.get("backendUrl") || "http://localhost:8000";
  };
  const apiClient = new ResearchPilotApiClient(tokenManager, getBackendUrl);

  // 3. Initialize Report Panel
  const reportPanel = new ReportPanel(context, apiClient);

  // 4. Initialize and Register Sidebar View Provider
  const sidebarProvider = new SidebarProvider(context, apiClient, reportPanel);
  const sidebarRegistration = vscode.window.registerWebviewViewProvider(
    "researchpilot.sidebar",
    sidebarProvider
  );
  context.subscriptions.push(sidebarRegistration);

  // 5. Register Extension Commands
  registerResearchCommands(context, apiClient, sidebarProvider, reportPanel);
  registerAuthCommands(context, apiClient, sidebarProvider);

  console.log("ResearchPilot extension active.");
}

function deactivate() {
  console.log("Deactivating ResearchPilot extension.");
}

module.exports = {
  activate,
  deactivate,
};

