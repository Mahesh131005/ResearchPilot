const { describe, it } = require("node:test");
const assert = require("node:assert");
const { formatApiError } = require("../src/utils/errorFormatter");

describe("ErrorFormatter Tests", () => {
  it("should format HTTP 429 quota errors with retry timing", () => {
    const errorBody = {
      error: "Hourly research submission quota exceeded",
      limit_type: "hourly_submissions",
      current_usage: 5,
      limit_value: 5,
      retry_after: 1200,
    };
    const formatted = formatApiError(429, errorBody);
    assert.match(formatted, /ResearchPilot Quota Exceeded \(hourly_submissions\)/);
    assert.match(formatted, /consumed 5 of 5/);
    assert.match(formatted, /Retry after 1200s/);
  });

  it("should format HTTP 503 billable operations emergency shutoff", () => {
    const errorBody = {
      detail: "Live billable operations are temporarily disabled by policy. Existing documents remain accessible.",
    };
    const formatted = formatApiError(503, errorBody);
    assert.match(formatted, /Billable Operations Paused/);
    assert.match(formatted, /temporarily disabled by policy/);
  });

  it("should format HTTP 402 insufficient wallet balance cleanly", () => {
    const errorBody = {
      detail: "Insufficient credit balance: A research inquiry requires a $0.05 estimated reservation hold.",
    };
    const formatted = formatApiError(402, errorBody);
    assert.match(formatted, /Payment Required/);
    assert.match(formatted, /reservation hold/);
  });

  it("should format HTTP 401 and 404 cleanly", () => {
    assert.strictEqual(
      formatApiError(401),
      "Authentication required or session expired. Please log in."
    );
    assert.strictEqual(
      formatApiError(404),
      "The requested research job or document was not found."
    );
  });

  it("should format HTTP 422 validation errors with field paths", () => {
    const errorBody = {
      detail: [
        { loc: ["body", "query"], msg: "String should have at least 5 characters" },
      ],
    };
    const formatted = formatApiError(422, errorBody);
    assert.match(formatted, /Validation Error: body\.query: String should have at least 5 characters/);
  });
});

