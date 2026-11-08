const { describe, it } = require("node:test");
const assert = require("node:assert");
const { SSEResearchStream } = require("../src/api/sse");

function createMockStream(chunks) {
  let index = 0;
  return {
    getReader() {
      return {
        async read() {
          if (index < chunks.length) {
            const encoder = new TextEncoder();
            const value = encoder.encode(chunks[index++]);
            return { value, done: false };
          }
          return { value: undefined, done: true };
        },
      };
    },
  };
}

describe("SSEResearchStream Tests", () => {
  it("should parse multi-line SSE milestone events and invoke callbacks", async () => {
    const rawChunks = [
      "event: milestone\ndata: {\"agent_name\": \"Planner Agent\", \"message\": \"Plan created\"}\n\n",
      "event: milestone\ndata: {\"agent_name\": \"Fact Checker Agent\", \"message\": \"Audit done\"}\n\n",
      "event: done\ndata: {}\n\n",
    ];

    const originalFetch = global.fetch;
    global.fetch = async () => ({
      ok: true,
      body: createMockStream(rawChunks),
    });

    try {
      const receivedEvents = [];
      let completed = false;

      const stream = new SSEResearchStream("http://test/stream", "fake_token", {
        onEvent: (ev) => receivedEvents.push(ev),
        onComplete: () => { completed = true; },
        onError: (err) => { assert.fail(err); },
      });

      await stream.start();

      assert.strictEqual(receivedEvents.length, 2);
      assert.strictEqual(receivedEvents[0].agent_name, "Planner Agent");
      assert.strictEqual(receivedEvents[0].message, "Plan created");
      assert.strictEqual(receivedEvents[1].agent_name, "Fact Checker Agent");
      assert.strictEqual(completed, true);
    } finally {
      global.fetch = originalFetch;
    }
  });

  it("should handle fragmented SSE buffers across chunk boundaries", async () => {
    // Stream split in the middle of a JSON line
    const rawChunks = [
      "event: milestone\ndata: {\"agent_name\": \"Document",
      " Research Agent\", \"message\": \"Found 4 chunks\"}\n\n",
      "event: done\ndata: {}\n\n",
    ];

    const originalFetch = global.fetch;
    global.fetch = async () => ({
      ok: true,
      body: createMockStream(rawChunks),
    });

    try {
      const receivedEvents = [];
      const stream = new SSEResearchStream("http://test/stream", "fake_token", {
        onEvent: (ev) => receivedEvents.push(ev),
      });

      await stream.start();

      assert.strictEqual(receivedEvents.length, 1);
      assert.strictEqual(receivedEvents[0].agent_name, "Document Research Agent");
      assert.strictEqual(receivedEvents[0].message, "Found 4 chunks");
    } finally {
      global.fetch = originalFetch;
    }
  });
});

