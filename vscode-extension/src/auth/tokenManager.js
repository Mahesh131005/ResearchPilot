/**
 * TokenManager
 * Manages secure persistent storage of JWT access and refresh tokens
 * using VS Code's native SecretStorage API.
 * Never exposes credentials to webview JavaScript.
 */

const ACCESS_TOKEN_KEY = "researchpilot.access_token";
const REFRESH_TOKEN_KEY = "researchpilot.refresh_token";
const USER_INFO_KEY = "researchpilot.user_info";

class TokenManager {
  /**
   * @param {import('vscode').SecretStorage} secrets
   */
  constructor(secrets) {
    this.secrets = secrets;
  }

  /**
   * Stores authentication tokens and basic user profile in SecretStorage.
   * @param {string} accessToken
   * @param {string} refreshToken
   * @param {object} user
   */
  async storeTokens(accessToken, refreshToken, user = null) {
    if (accessToken) {
      await this.secrets.store(ACCESS_TOKEN_KEY, accessToken);
    }
    if (refreshToken) {
      await this.secrets.store(REFRESH_TOKEN_KEY, refreshToken);
    }
    if (user) {
      await this.secrets.store(USER_INFO_KEY, JSON.stringify(user));
    }
  }

  /**
   * Retrieves the current access token.
   * @returns {Promise<string|undefined>}
   */
  async getAccessToken() {
    return await this.secrets.get(ACCESS_TOKEN_KEY);
  }

  /**
   * Retrieves the current refresh token.
   * @returns {Promise<string|undefined>}
   */
  async getRefreshToken() {
    return await this.secrets.get(REFRESH_TOKEN_KEY);
  }

  /**
   * Retrieves cached user profile.
   * @returns {Promise<object|null>}
   */
  async getUserInfo() {
    const raw = await this.secrets.get(USER_INFO_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  /**
   * Checks if an access token exists.
   * @returns {Promise<boolean>}
   */
  async isAuthenticated() {
    const token = await this.getAccessToken();
    return Boolean(token && token.trim().length > 0);
  }

  /**
   * Clears all stored tokens and user profile upon logout or session invalidation.
   */
  async clearTokens() {
    await this.secrets.delete(ACCESS_TOKEN_KEY);
    await this.secrets.delete(REFRESH_TOKEN_KEY);
    await this.secrets.delete(USER_INFO_KEY);
  }
}

module.exports = { TokenManager };

