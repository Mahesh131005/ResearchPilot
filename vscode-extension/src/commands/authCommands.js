/**
 * AuthCommands
 * Handles VS Code Command Palette interactions for login, logout, and quota views.
 */

const vscode = require("vscode");

/**
 * Registers authentication and quota commands.
 * @param {vscode.ExtensionContext} context
 * @param {import('../api/client').ResearchPilotApiClient} apiClient
 * @param {import('../views/sidebarProvider').SidebarProvider} sidebarProvider
 */
function registerAuthCommands(context, apiClient, sidebarProvider) {
  // 1. Log In Command
  const loginCmd = vscode.commands.registerCommand("researchpilot.login", async () => {
    const email = await vscode.window.showInputBox({
      title: "ResearchPilot: Account Login",
      prompt: "Enter your registered email address",
      placeHolder: "user@example.com",
      validateInput: (v) => (!v || !v.includes("@") ? "Please enter a valid email." : null),
    });

    if (!email) return;

    const password = await vscode.window.showInputBox({
      title: "ResearchPilot: Account Login",
      prompt: "Enter your password",
      password: true,
      validateInput: (v) => (!v ? "Password cannot be empty." : null),
    });

    if (!password) return;

    const res = await apiClient.login(email, password);
    if (!res.success) {
      vscode.window.showErrorMessage(`Login failed: ${res.error}`);
    } else {
      vscode.window.showInformationMessage(`Successfully logged in as ${res.user.email}`);
      await sidebarProvider.syncState();
    }
  });

  // 2. Log Out Command
  const logoutCmd = vscode.commands.registerCommand("researchpilot.logout", async () => {
    await apiClient.tokenManager.clearTokens();
    vscode.window.showInformationMessage("Logged out of ResearchPilot.");
    await sidebarProvider.syncState();
  });

  // 3. View Quota & Usage Command
  const viewUsageCmd = vscode.commands.registerCommand("researchpilot.viewUsage", async () => {
    const isAuth = await apiClient.tokenManager.isAuthenticated();
    if (!isAuth) {
      vscode.window.showWarningMessage("Please log in to view your research quotas and usage metrics.");
      return;
    }

    try {
      const usage = await apiClient.getUsage();
      const dailyUsed = usage.daily_jobs_used || 0;
      const dailyLimit = usage.limits ? usage.limits.daily_jobs_limit : 10;
      const monthlyUsed = usage.monthly_jobs_used || 0;
      const monthlyLimit = usage.limits ? usage.limits.monthly_jobs_limit : 100;
      const tokensTotal = usage.total_tokens ? usage.total_tokens.toLocaleString() : "0";
      const searchesTotal = usage.total_web_searches || 0;

      vscode.window.showInformationMessage(
        `ResearchPilot Quota Summary:\n` +
        `• Daily Jobs: ${dailyUsed} / ${dailyLimit}\n` +
        `• Monthly Jobs: ${monthlyUsed} / ${monthlyLimit}\n` +
        `• Gemini Tokens: ${tokensTotal}\n` +
        `• Tavily Searches: ${searchesTotal}`,
        { modal: true }
      );
    } catch (err) {
      vscode.window.showErrorMessage(`Failed to fetch usage: ${err.message}`);
    }
  });

  // 4. Refresh History Command
  const refreshHistoryCmd = vscode.commands.registerCommand("researchpilot.refreshHistory", async () => {
    await sidebarProvider.syncState();
    vscode.window.showInformationMessage("Research history refreshed.");
  });

  context.subscriptions.push(loginCmd, logoutCmd, viewUsageCmd, refreshHistoryCmd);
}

module.exports = { registerAuthCommands };

