import { describe, it, expect } from "vitest";

function resolveApiBaseUrl(rawApiUrl) {
  let normalizedHost = rawApiUrl ? String(rawApiUrl).trim() : "";
  if (normalizedHost) {
    if (!normalizedHost.startsWith("http://") && !normalizedHost.startsWith("https://")) {
      normalizedHost = `https://${normalizedHost}`;
    }
    normalizedHost = normalizedHost.replace(/\/api\/v1\/?$/, "").replace(/\/+$/, "");
  }
  return normalizedHost ? `${normalizedHost}/api/v1` : "/api/v1";
}

describe("API Base URL Normalization", () => {
  it("resolves production URL without trailing slash", () => {
    const url = resolveApiBaseUrl("https://researchpilot-api-cb0c.onrender.com");
    expect(url).toBe("https://researchpilot-api-cb0c.onrender.com/api/v1");
  });

  it("resolves production URL with trailing slash", () => {
    const url = resolveApiBaseUrl("https://researchpilot-api-cb0c.onrender.com/");
    expect(url).toBe("https://researchpilot-api-cb0c.onrender.com/api/v1");
  });

  it("resolves production URL already having /api/v1 without double appending", () => {
    const url = resolveApiBaseUrl("https://researchpilot-api-cb0c.onrender.com/api/v1");
    expect(url).toBe("https://researchpilot-api-cb0c.onrender.com/api/v1");
  });

  it("prepends https:// if hostname is passed without scheme", () => {
    const url = resolveApiBaseUrl("researchpilot-api-cb0c.onrender.com");
    expect(url).toBe("https://researchpilot-api-cb0c.onrender.com/api/v1");
  });

  it("preserves local development fallback when VITE_API_URL is empty", () => {
    const url = resolveApiBaseUrl("");
    expect(url).toBe("/api/v1");
  });

  it("preserves local development localhost URL when explicitly passed", () => {
    const url = resolveApiBaseUrl("http://127.0.0.1:8000");
    expect(url).toBe("http://127.0.0.1:8000/api/v1");
  });
});

