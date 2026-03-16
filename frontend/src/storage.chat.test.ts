import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createChatSession, loadChatSessionStore, saveChatSessionStore } from "./storage";

function createMemoryStorage(): Storage {
  const store: Record<string, string> = {};
  return {
    getItem: (key: string) => (key in store ? store[key] : null),
    setItem: (key: string, value: string) => {
      store[key] = String(value);
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      Object.keys(store).forEach((key) => delete store[key]);
    },
    key: (index: number) => Object.keys(store)[index] ?? null,
    get length() {
      return Object.keys(store).length;
    },
  };
}

describe("chat session storage", () => {
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    warnSpy = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: createMemoryStorage(),
    });
  });

  afterEach(() => {
    warnSpy.mockRestore();
  });

  it("creates a default session when storage is empty", () => {
    const store = loadChatSessionStore();
    expect(store.sessions.length).toBe(1);
    expect(store.activeSessionId).toBe(store.sessions[0].id);
    expect(store.sessions[0].messages).toEqual([]);
  });

  it("persists and restores sessions", () => {
    const first = createChatSession(new Date("2026-03-16T00:00:00.000Z"));
    first.title = "Session A";
    first.messages = [{ role: "user", content: "hello" }];

    const second = createChatSession(new Date("2026-03-16T01:00:00.000Z"));
    second.title = "Session B";

    saveChatSessionStore({
      activeSessionId: second.id,
      sessions: [first, second],
    });

    const restored = loadChatSessionStore();
    expect(restored.sessions).toHaveLength(2);
    expect(restored.activeSessionId).toBe(second.id);
    expect(restored.sessions[0].title).toBe("Session A");
    expect(restored.sessions[0].messages[0]?.content).toBe("hello");
  });

  it("falls back to first session when active id is invalid", () => {
    const first = createChatSession(new Date("2026-03-16T00:00:00.000Z"));
    first.title = "Only Session";

    localStorage.setItem(
      "paper-agent-chat-sessions",
      JSON.stringify({
        activeSessionId: "missing-session-id",
        sessions: [first],
      }),
    );

    const restored = loadChatSessionStore();
    expect(restored.activeSessionId).toBe(first.id);
  });

  it("recovers from malformed payload", () => {
    localStorage.setItem("paper-agent-chat-sessions", "not-json");
    const restored = loadChatSessionStore();
    expect(restored.sessions.length).toBe(1);
  });
});
