const { describe, it, beforeEach } = require("node:test");
const assert = require("node:assert");
const { TokenManager } = require("../src/auth/tokenManager");

class MockSecretStorage {
  constructor() {
    this.storeMap = new Map();
  }
  async get(key) {
    return this.storeMap.get(key);
  }
  async store(key, value) {
    this.storeMap.set(key, value);
  }
  async delete(key) {
    this.storeMap.delete(key);
  }
}

describe("TokenManager Tests", () => {
  let mockSecrets;
  let tokenManager;

  beforeEach(() => {
    mockSecrets = new MockSecretStorage();
    tokenManager = new TokenManager(mockSecrets);
  });

  it("should initialize unauthenticated", async () => {
    const isAuth = await tokenManager.isAuthenticated();
    assert.strictEqual(isAuth, false);
    assert.strictEqual(await tokenManager.getAccessToken(), undefined);
    assert.strictEqual(await tokenManager.getRefreshToken(), undefined);
    assert.strictEqual(await tokenManager.getUserInfo(), null);
  });

  it("should securely store and retrieve access and refresh tokens", async () => {
    const user = { id: "u-123", email: "test@example.com", role: "user" };
    await tokenManager.storeTokens("access_jwt_123", "refresh_jwt_456", user);

    assert.strictEqual(await tokenManager.isAuthenticated(), true);
    assert.strictEqual(await tokenManager.getAccessToken(), "access_jwt_123");
    assert.strictEqual(await tokenManager.getRefreshToken(), "refresh_jwt_456");

    const retrievedUser = await tokenManager.getUserInfo();
    assert.deepStrictEqual(retrievedUser, user);
  });

  it("should cleanly clear all tokens upon logout", async () => {
    await tokenManager.storeTokens("acc", "ref", { email: "a@b.com" });
    assert.strictEqual(await tokenManager.isAuthenticated(), true);

    await tokenManager.clearTokens();
    assert.strictEqual(await tokenManager.isAuthenticated(), false);
    assert.strictEqual(await tokenManager.getAccessToken(), undefined);
    assert.strictEqual(await tokenManager.getRefreshToken(), undefined);
    assert.strictEqual(await tokenManager.getUserInfo(), null);
  });
});

