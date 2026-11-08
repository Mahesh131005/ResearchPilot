const { describe, it, beforeEach } = require("node:test");
const assert = require("node:assert");
const { ResearchPilotApiClient } = require("../src/api/client");
const { TokenManager } = require("../src/auth/tokenManager");

class MockSecretStorage {
  constructor() {
    this.storeMap = new Map();
  }
  async get(k) { return this.storeMap.get(k); }
  async store(k, v) { this.storeMap.set(k, v); }
  async delete(k) { this.storeMap.delete(k); }
}

describe("ResearchPilotApiClient Tests", () => {
  let mockSecrets;
  let tokenManager;
  let client;

  beforeEach(() => {
    mockSecrets = new MockSecretStorage();
    tokenManager = new TokenManager(mockSecrets);
    client = new ResearchPilotApiClient(tokenManager, () => "http://127.0.0.1:8000");
  });

  it("should construct normalized absolute URLs correctly", () => {
    assert.strictEqual(client.url("api/v1/health"), "http://127.0.0.1:8000/api/v1/health");
    assert.strictEqual(client.url("/api/v1/research/jobs"), "http://127.0.0.1:8000/api/v1/research/jobs");
  });

  it("should handle login and securely store tokens", async () => {
    const originalFetch = global.fetch;
    global.fetch = async (url, opts) => {
      assert.strictEqual(url, "http://127.0.0.1:8000/api/v1/auth/login");
      assert.strictEqual(opts.method, "POST");
      return {
        ok: true,
        status: 200,
        json: async () => ({
          access_token: "test_access_jwt",
          refresh_token: "test_refresh_jwt",
          user: { id: "u-1", email: "user@test.com", role: "user" },
        }),
      };
    };

    try {
      const res = await client.login("user@test.com", "SecretPass123!");
      assert.strictEqual(res.success, true);
      assert.strictEqual(res.user.email, "user@test.com");
      assert.strictEqual(await tokenManager.getAccessToken(), "test_access_jwt");
      assert.strictEqual(await tokenManager.getRefreshToken(), "test_refresh_jwt");
    } finally {
      global.fetch = originalFetch;
    }
  });

  it("should catch HTTP 429 quota exhaustion and return formatted error", async () => {
    const originalFetch = global.fetch;
    global.fetch = async () => ({
      ok: false,
      status: 429,
      json: async () => ({
        error: "Daily research job limit reached",
        limit_type: "daily_jobs",
        current_usage: 10,
        limit_value: 10,
        retry_after: 3600,
      }),
    });

    try {
      await tokenManager.storeTokens("valid_token", "ref_token");
      const res = await client.createJob({ query: "Test research topic" });
      assert.strictEqual(res.success, false);
      assert.strictEqual(res.status, 429);
      assert.match(res.error, /ResearchPilot Quota Exceeded \(daily_jobs\)/);
      assert.match(res.error, /consumed 10 of 10/);
      assert.match(res.error, /Retry after 3600s/);
    } finally {
      global.fetch = originalFetch;
    }
  });

  it("should catch HTTP 503 emergency billable shutoff", async () => {
    const originalFetch = global.fetch;
    global.fetch = async () => ({
      ok: false,
      status: 503,
      json: async () => ({
        detail: "Live billable operations are temporarily disabled by policy. Existing documents remain accessible.",
      }),
    });

    try {
      await tokenManager.storeTokens("valid_token", "ref_token");
      const res = await client.createJob({ query: "Test research topic" });
      assert.strictEqual(res.success, false);
      assert.strictEqual(res.status, 503);
      assert.match(res.error, /Billable Operations Paused/);
    } finally {
      global.fetch = originalFetch;
    }
  });

  it("should retry request once upon 401 when token refresh succeeds", async () => {
    let callCount = 0;
    const originalFetch = global.fetch;
    global.fetch = async (url, opts) => {
      callCount++;
      if (url.includes("/api/v1/auth/refresh")) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            access_token: "new_rotated_access_token",
            refresh_token: "new_rotated_refresh_token",
            user: { id: "u-1", email: "user@test.com" },
          }),
        };
      }
      if (callCount === 1) {
        // First attempt expired
        return { ok: false, status: 401, json: async () => ({ detail: "Token expired" }) };
      }
      // Second attempt with refreshed token
      assert.strictEqual(opts.headers.Authorization, "Bearer new_rotated_access_token");
      return {
        ok: true,
        status: 200,
        json: async () => ([{ id: "job-1", status: "completed" }]),
      };
    };

    try {
      await tokenManager.storeTokens("old_expired_token", "valid_refresh_token");
      const jobs = await client.listJobs();
      assert.strictEqual(jobs.length, 1);
      assert.strictEqual(jobs[0].id, "job-1");
      assert.strictEqual(await tokenManager.getAccessToken(), "new_rotated_access_token");
    } finally {
      global.fetch = originalFetch;
    }
  });
});

