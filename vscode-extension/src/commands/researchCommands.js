/**
 * ResearchCommands
 * Implements editor context actions, selection research, and markdown saving.
 */

const vscode = require("vscode");

/**
 * Registers research-related commands.
 * @param {vscode.ExtensionContext} context
 * @param {import('../api/client').ResearchPilotApiClient} apiClient
 * @param {import('../views/sidebarProvider').SidebarProvider} sidebarProvider
 * @param {import('../views/reportPanel').ReportPanel} reportPanel
 */
function registerResearchCommands(context, apiClient, sidebarProvider, reportPanel) {
  // 1. Research Selected Text Command
  const researchSelectionCmd = vscode.commands.registerCommand(
    "researchpilot.researchSelection",
    async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showWarningMessage("No active editor found.");
        return;
      }

      const selection = editor.selection;
      const text = editor.document.getText(selection).trim();

      if (!text || text.length < 5) {
        vscode.window.showWarningMessage("Please select at least 5 characters of text to research.");
        return;
      }

      if (text.length > 20000) {
        const proceed = await vscode.window.showWarningMessage(
          `Selected text is unusually large (${text.length.toLocaleString()} characters). To maintain research precision and avoid token flooding, it will be bounded to the first 20,000 characters (~5,000 words). Continue?`,
          { modal: true },
          "Continue with Excerpt",
          "Cancel"
        );
        if (proceed !== "Continue with Excerpt") {
          return;
        }
      }
      const queryText = text.slice(0, 20000);

      // Explicit consent confirmation before submitting selected code or document text
      const preview = queryText.length > 80 ? queryText.slice(0, 80) + "..." : queryText;
      const confirm = await vscode.window.showInformationMessage(
        `Submit selected text to ResearchPilot multi-agent engine?\n\n"${preview}"`,
        { modal: true },
        "Start Research",
        "Cancel"
      );

      if (confirm !== "Start Research") {
        return;
      }

      // Check authentication
      const isAuth = await apiClient.tokenManager.isAuthenticated();
      if (!isAuth) {
        const loginAction = await vscode.window.showWarningMessage(
          "You must log in to ResearchPilot before launching research.",
          "Log In"
        );
        if (loginAction === "Log In") {
          vscode.commands.executeCommand("researchpilot.login");
        }
        return;
      }

      // Reveal sidebar and dispatch research
      await vscode.commands.executeCommand("researchpilot.sidebar.focus");
      await sidebarProvider.handleStartResearch({
        query: queryText,
        depth: vscode.workspace.getConfiguration("researchpilot").get("defaultDepth", "standard"),
        enableWeb: vscode.workspace.getConfiguration("researchpilot").get("enableWeb", true),
        enableDocuments: vscode.workspace.getConfiguration("researchpilot").get("enableDocuments", true),
      });
    }
  );

  // 2. Start New Research via QuickPick / InputBox
  const startResearchCmd = vscode.commands.registerCommand(
    "researchpilot.startResearch",
    async () => {
      const query = await vscode.window.showInputBox({
        title: "ResearchPilot: New Research Inquiry",
        prompt: "Enter your complex research inquiry or technical evaluation question",
        placeHolder: "e.g., Empirical comparison of MA-ALNS vs standard ALNS in link routing optimization",
        validateInput: (val) => (!val || val.trim().length < 5 ? "Query must be at least 5 characters." : null),
      });

      if (!query) return;

      const depth = await vscode.window.showQuickPick(
        [
          { label: "standard", description: "Standard in-depth multi-agent synthesis (Recommended)" },
          { label: "quick", description: "Fast overview" },
          { label: "deep", description: "Comprehensive multi-round verification" },
        ],
        { title: "Select Research Depth" }
      );

      if (!depth) return;

      await vscode.commands.executeCommand("researchpilot.sidebar.focus");
      await sidebarProvider.handleStartResearch({
        query,
        depth: depth.label,
        enableWeb: vscode.workspace.getConfiguration("researchpilot").get("enableWeb", true),
        enableDocuments: vscode.workspace.getConfiguration("researchpilot").get("enableDocuments", true),
      });
    }
  );

  // 3. Save Active Report as Markdown
  const saveReportCmd = vscode.commands.registerCommand(
    "researchpilot.saveReportMarkdown",
    async () => {
      if (reportPanel) {
        await reportPanel.saveMarkdown();
      } else {
        vscode.window.showInformationMessage("No active report panel open to save.");
      }
    }
  );

  context.subscriptions.push(researchSelectionCmd, startResearchCmd, saveReportCmd);
}

module.exports = { registerResearchCommands };

