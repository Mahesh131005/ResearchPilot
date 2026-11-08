/**
 * SSEResearchStream
 * Client for consuming Server-Sent Events from ResearchPilot's live progress API.
 */

class SSEResearchStream {
  /**
   * @param {string} url
   * @param {string} token
   * @param {object} callbacks
   * @param {function(object): void} callbacks.onEvent
   * @param {function(): void} [callbacks.onComplete]
   * @param {function(Error): void} [callbacks.onError]
   */
  constructor(url, token, { onEvent, onComplete, onError }) {
    this.url = url;
    this.token = token;
    this.onEvent = onEvent || (() => {});
    this.onComplete = onComplete || (() => {});
    this.onError = onError || (() => {});
    this.abortController = new AbortController();
  }

  /**
   * Starts listening to the SSE stream.
   */
  async start() {
    try {
      const headers = {
        "Accept": "text/event-stream",
        "Cache-Control": "no-cache",
      };
      if (this.token) {
        headers["Authorization"] = `Bearer ${this.token}`;
      }

      const response = await fetch(this.url, {
        headers,
        signal: this.abortController.signal,
      });

      if (!response.ok) {
        let errBody = {};
        try {
          errBody = await response.json();
        } catch {}
        const error = new Error(`SSE stream connection failed with HTTP ${response.status}`);
        error.status = response.status;
        error.body = errBody;
        this.onError(error);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let currentEvent = "message";
      let currentData = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop(); // Keep partial line in buffer

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) {
            // Empty line marks end of event
            if (currentData) {
              this._dispatch(currentEvent, currentData);
              currentEvent = "message";
              currentData = "";
            }
            continue;
          }

          if (trimmed.startsWith("event:")) {
            currentEvent = trimmed.slice(6).trim();
          } else if (trimmed.startsWith("data:")) {
            currentData += (currentData ? "\n" : "") + trimmed.slice(5).trim();
          }
        }
      }

      // Flush remaining data if present
      if (currentData) {
        this._dispatch(currentEvent, currentData);
      }

      this.onComplete();
    } catch (err) {
      if (err.name === "AbortError") {
        // Stream aborted cleanly
        return;
      }
      this.onError(err);
    }
  }

  _dispatch(eventName, rawData) {
    if (eventName === "done") {
      this.onComplete();
      return;
    }

    try {
      const parsed = JSON.parse(rawData);
      this.onEvent(parsed);
    } catch {
      this.onEvent({ message: rawData, event_type: eventName });
    }
  }

  /**
   * Aborts the active SSE stream.
   */
  abort() {
    this.abortController.abort();
  }
}

module.exports = { SSEResearchStream };
