/**
 * ResearchPilotApiClient
 * Shared client for FastAPI REST and SSE endpoints with automatic JWT token management,
 * refresh rotation, 429 rate limit diagnostics, and 503 emergency policy interception.
 */

const { formatApiError } = require("../utils/errorFormatter");

class ResearchPilotApiClient {
  /**
   * @param {import('../auth/tokenManager').TokenManager} tokenManager
   * @param {function(): string} getBaseUrl
   */
  constructor(tokenManager, getBaseUrl) {
    this.tokenManager = tokenManager;
    this.getBaseUrl = getBaseUrl || (() => "http://localhost:8000");
  }

  /**
   * Constructs an absolute URL for an API endpoint.
   * @param {string} path
   * @returns {string}
   */
  url(path) {
    const base = this.getBaseUrl().replace(/\/+$/, "");
    const cleanPath = path.replace(/^\/+/, "");
    return `${base}/${cleanPath}`;
  }

  /**
   * Verifies backend connectivity via health endpoint.
   * @returns {Promise<{ ok: boolean, status: string, error?: string }>}
   */
  async checkHealth() {
    try {
      const res = await fetch(this.url("api/v1/health"), { method: "GET" });
      if (res.ok) {
        const data = await res.json();
        return { ok: true, status: data.status || "healthy" };
      }
      return { ok: false, status: `HTTP ${res.status}` };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  /**
   * Authenticates user with credentials and persists tokens in SecretStorage.
   * @param {string} email
   * @param {string} password
   * @returns {Promise<{ success: boolean, user?: object, error?: string }>}
   */
  async login(email, password) {
    try {
      const res = await fetch(this.url("api/v1/auth/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        return { success: false, error: formatApiError(res.status, body) };
      }

      await this.tokenManager.storeTokens(body.access_token, body.refresh_token, body.user);
      return { success: true, user: body.user };
    } catch (e) {
      return { success: false, error: `Login network failure: ${e.message}` };
    }
  }

  /**
   * Registers a new account.
   * @param {string} email
   * @param {string} password
   * @param {string} fullName
   * @returns {Promise<{ success: boolean, user?: object, error?: string }>}
   */
  async register(email, password, fullName) {
    try {
      const res = await fetch(this.url("api/v1/auth/register"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, full_name: fullName }),
      });

      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        return { success: false, error: formatApiError(res.status, body) };
      }

      await this.tokenManager.storeTokens(body.access_token, body.refresh_token, body.user);
      return { success: true, user: body.user };
    } catch (e) {
      return { success: false, error: `Registration failure: ${e.message}` };
    }
  }

  /**
   * Rotates refresh token to obtain a fresh access token.
   * @returns {Promise<boolean>}
   */
  async refreshAccessToken() {
    const refreshToken = await this.tokenManager.getRefreshToken();
    if (!refreshToken) return false;

    try {
      const res = await fetch(this.url("api/v1/auth/refresh"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!res.ok) {
        await this.tokenManager.clearTokens();
        return false;
      }

      const body = await res.json();
      await this.tokenManager.storeTokens(body.access_token, body.refresh_token, body.user);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Executes an authenticated request with bearer token attachment and 401 refresh retry.
   * @param {string} path
   * @param {RequestInit} [options={}]
   * @returns {Promise<Response>}
   */
  async authenticatedFetch(path, options = {}) {
    let token = await this.tokenManager.getAccessToken();

    const headers = {
      ...(options.headers || {}),
      "Authorization": `Bearer ${token || ""}`,
    };

    let response = await fetch(this.url(path), { ...options, headers });

    // Handle 401 token expiration with single refresh attempt
    if (response.status === 401) {
      const refreshed = await this.refreshAccessToken();
      if (refreshed) {
        token = await this.tokenManager.getAccessToken();
        headers["Authorization"] = `Bearer ${token}`;
        response = await fetch(this.url(path), { ...options, headers });
      }
    }

    return response;
  }

  /**
   * Submits a new research job.
   * Returns { success, job, error }
   */
  async createJob({ query, depth = "standard", enableWeb = true, enableDocuments = true, documentIds = [] }) {
    try {
      const payload = {
        query,
        depth,
        enable_web: enableWeb,
        enable_documents: enableDocuments,
        document_ids: documentIds,
      };

      const res = await this.authenticatedFetch("api/v1/research/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        return { success: false, error: formatApiError(res.status, body), status: res.status, body };
      }

      return { success: true, job: body };
    } catch (e) {
      return { success: false, error: `Job submission failed: ${e.message}` };
    }
  }

  /**
   * Fetches single job status.
   */
  async getJob(jobId) {
    const res = await this.authenticatedFetch(`api/v1/research/jobs/${jobId}`);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(formatApiError(res.status, body));
    }
    return await res.json();
  }

  /**
   * Fetches research jobs history for authenticated user.
   */
  async listJobs() {
    const res = await this.authenticatedFetch("api/v1/research/jobs");
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(formatApiError(res.status, body));
    }
    return await res.json();
  }

  /**
   * Fetches the completed analytical report for a job.
   */
  async getReport(jobId) {
    const res = await this.authenticatedFetch(`api/v1/research/jobs/${jobId}/report`);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(formatApiError(res.status, body));
    }
    return await res.json();
  }

  /**
   * Fetches authenticated user's current rate limits and quota allocations.
   */
  async getUsage() {
    const res = await this.authenticatedFetch("api/v1/usage/me");
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(formatApiError(res.status, body));
    }
    return await res.json();
  }

  /**
   * Fetches uploaded document knowledge base for document selection.
   */
  async getDocuments() {
    const res = await this.authenticatedFetch("api/v1/documents");
    if (!res.ok) {
      return [];
    }
    return await res.json();
  }

  /**
   * Fetches user credit wallet balance and reservation status.
   */
  async getWallet() {
    const res = await this.authenticatedFetch("api/v1/billing/wallet");
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(formatApiError(res.status, body));
    }
    return await res.json();
  }
}

module.exports = { ResearchPilotApiClient };

