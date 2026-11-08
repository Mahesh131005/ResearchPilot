/**
 * ErrorFormatter
 * Formats API errors and HTTP status codes into clear, actionable messages for the user.
 */

function formatApiError(responseStatus, responseBody = {}) {
  const detail = responseBody.detail || responseBody.message || responseBody.error;

  switch (responseStatus) {
    case 429: {
      const limitType = responseBody.limit_type || "rate limit";
      const current = responseBody.current_usage !== undefined ? responseBody.current_usage : "";
      const limit = responseBody.limit_value !== undefined ? responseBody.limit_value : "";
      const retryAfter = responseBody.retry_after;

      let msg = `ResearchPilot Quota Exceeded (${limitType})`;
      if (current && limit) {
        msg += `: consumed ${current} of ${limit}`;
      }
      if (retryAfter) {
        msg += `. Retry after ${retryAfter}s.`;
      } else if (detail) {
        msg += `: ${detail}`;
      }
      return msg;
    }

    case 503: {
      if (detail && detail.includes("billable")) {
        return `Billable Operations Paused: ${detail}`;
      }
      return `Service Unavailable: ${detail || "Backend service is temporarily unavailable."}`;
    }

    case 401:
      return "Authentication required or session expired. Please log in.";

    case 402:
      return `Payment Required: ${detail || "Insufficient credit balance. Please top up your wallet in the web dashboard."}`;

    case 403:
      return `Access denied: ${detail || "You do not have permission to perform this action."}`;

    case 404:
      return "The requested research job or document was not found.";

    case 422: {
      if (Array.isArray(detail)) {
        const fieldErrors = detail.map(d => `${d.loc ? d.loc.join('.') : 'field'}: ${d.msg}`).join("; ");
        return `Validation Error: ${fieldErrors}`;
      }
      return `Validation Error: ${detail || "Invalid input parameters."}`;
    }

    default:
      return detail || `Request failed with HTTP ${responseStatus}.`;
  }
}

module.exports = { formatApiError };

