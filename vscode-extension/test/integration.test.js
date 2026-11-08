const { describe, it, before, after } = require("node:test");
const assert = require("node:assert");
const http = require("node:http");
const { TokenManager } = require("../src/auth/tokenManager");
const { ResearchPilotApiClient } = require("../src/api/client");
const { SSEResearchStream } = require("../src/api/sse");

class MemorySecretStorage {
  constructor() {
    this.map = new Map();
  }
  async get(k) { return this.map.get(k); }
  async store(k, v) { this.map.set(k, v); }
  async delete(k) { this.map.delete(k); }
}

describe("VS Code Extension Live Wire-Level Integration Tests", () => {
  let server;
  let serverPort;
  let tokenManager;
  let apiClient;
  let refreshCount = 0;

  before(async () => {
    await new Promise((resolve) => {
      // Spin up a live HTTP server simulating the exact FastAPI backend wire protocol
      server = http.createServer((req, res) => {
        const url = new URL(req.url, `http://localhost:${serverPort}`);

        if (url.pathname === "/api/v1/health") {
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ status: "healthy", version: "1.0.0" }));
          return;
        }

        if (url.pathname === "/api/v1/auth/login" && req.method === "POST") {
          let body = "";
          req.on("data", chunk => body += chunk);
          req.on("end", () => {
            const { email, password } = JSON.parse(body);
            if (email === "test@researchpilot.local" && password === "ValidPass123!") {
              res.writeHead(200, { "Content-Type": "application/json" });
              res.end(JSON.stringify({
                access_token: "jwt_access_initial",
                refresh_token: "jwt_refresh_initial",
                token_type: "bearer"
              }));
            } else {
              res.writeHead(401, { "Content-Type": "application/json" });
              res.end(JSON.stringify({ detail: "Invalid credentials" }));
            }
          });
          return;
        }

        if (url.pathname === "/api/v1/auth/refresh" && req.method === "POST") {
          refreshCount++;
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify({
            access_token: "jwt_access_rotated",
            refresh_token: "jwt_refresh_rotated",
            token_type: "bearer"
          }));
          return;
        }

        if (url.pathname === "/api/v1/billing/wallet") {
          const authHeader = req.headers["authorization"];
          if (authHeader === "Bearer jwt_access_initial") {
            // Trigger a 401 to test automatic token rotation over the wire
            res.writeHead(401, { "Content-Type": "application/json" });
            res.end(JSON.stringify({ detail: "Token expired" }));
            return;
          }
          if (authHeader === "Bearer jwt_access_rotated") {
            res.writeHead(200, { "Content-Type": "application/json" });
            res.end(JSON.stringify({
              balance_usd: 1.00,
              reserved_usd: 0.05,
              available_balance_usd: 0.95,
              lifetime_spent_usd: 0.12,
              tier: "free"
            }));
            return;
          }
          res.writeHead(401, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ detail: "Unauthorized" }));
          return;
        }

        if (url.pathname.startsWith("/api/v1/research/jobs/") && url.pathname.endsWith("/stream")) {
          // Real HTTP Server-Sent Events stream over TCP
          res.writeHead(200, {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
          });

          res.write("event: milestone\ndata: {\"agent_name\": \"Planner\", \"message\": \"Decomposed inquiry into 3 sub-questions\"}\n\n");
          setTimeout(() => {
            res.write("event: milestone\ndata: {\"agent_name\": \"FactChecker\", \"message\": \"Verified 4 factual claims\"}\n\n");
            res.write("event: complete\ndata: {\"job_id\": \"job-live-123\", \"status\": \"completed\"}\n\n");
            res.end();
          }, 50);
          return;
        }

        res.writeHead(404, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ detail: "Not found" }));
      });

      server.listen(0, "127.0.0.1", () => {
        serverPort = server.address().port;
        tokenManager = new TokenManager(new MemorySecretStorage());
        apiClient = new ResearchPilotApiClient(tokenManager, () => `http://127.0.0.1:${serverPort}`);
        resolve();
      });
    });
  });

  after(async () => {
    if (server) {
      await new Promise((resolve) => server.close(resolve));
    }
  });

  it("should verify live backend liveness over TCP socket", async () => {
    const health = await apiClient.checkHealth();
    assert.strictEqual(health.ok, true);
    assert.strictEqual(health.status, "healthy");
  });

  it("should authenticate and persist tokens over TCP socket", async () => {
    const loginRes = await apiClient.login("test@researchpilot.local", "ValidPass123!");
    assert.strictEqual(loginRes.success, true);
    assert.strictEqual(await tokenManager.isAuthenticated(), true);
    assert.strictEqual(await tokenManager.getAccessToken(), "jwt_access_initial");
  });

  it("should transparently rotate access and refresh tokens upon 401 over live TCP", async () => {
    assert.strictEqual(refreshCount, 0);

    // Calling getWallet will receive 401 with initial token, trigger refresh, and retry with rotated token
    const wallet = await apiClient.getWallet();
    assert.strictEqual(refreshCount, 1);
    assert.strictEqual(wallet.balance_usd, 1.00);
    assert.strictEqual(wallet.available_balance_usd, 0.95);

    // Verify SecretStorage was updated with rotated tokens
    assert.strictEqual(await tokenManager.getAccessToken(), "jwt_access_rotated");
    assert.strictEqual(await tokenManager.getRefreshToken(), "jwt_refresh_rotated");
  });

  it("should consume real chunked Server-Sent Events over live TCP stream", async () => {
    const streamUrl = apiClient.url("api/v1/research/jobs/job-live-123/stream");
    const token = await tokenManager.getAccessToken();

    const eventsReceived = [];
    let completed = false;

    await new Promise((resolve, reject) => {
      const stream = new SSEResearchStream(streamUrl, token, {
        onEvent: (ev) => {
          eventsReceived.push(ev);
        },
        onComplete: () => {
          completed = true;
          resolve();
        },
        onError: (err) => {
          reject(err);
        }
      });
      stream.start();
    });

    assert.strictEqual(completed, true);
    assert.strictEqual(eventsReceived.length, 3);
    assert.strictEqual(eventsReceived[0].agent_name, "Planner");
    assert.strictEqual(eventsReceived[1].agent_name, "FactChecker");
    assert.strictEqual(eventsReceived[2].job_id, "job-live-123");
  });
});
