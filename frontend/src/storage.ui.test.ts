import { beforeEach, describe, expect, it } from "vitest";

import { defaultUiPreferences, loadUiPreferences, saveUiPreferences } from "./storage";

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

describe("UI preferences storage", () => {
  beforeEach(() => {
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: createMemoryStorage(),
    });
  });

  it("returns dark theme by default", () => {
    expect(loadUiPreferences()).toEqual(defaultUiPreferences);
  });

  it("persists and restores theme value", () => {
    saveUiPreferences({ theme: "light" });
    expect(loadUiPreferences()).toEqual({ theme: "light" });
  });

  it("falls back to dark theme for invalid payload", () => {
    localStorage.setItem("paper-agent-ui-preferences", JSON.stringify({ theme: "unknown" }));
    expect(loadUiPreferences()).toEqual({ theme: "dark" });
  });
});
