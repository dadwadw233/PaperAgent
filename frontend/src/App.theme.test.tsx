import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mockLoadSettings = vi.fn();
const mockSaveSettings = vi.fn();
const mockLoadUiPreferences = vi.fn();
const mockSaveUiPreferences = vi.fn();

vi.mock("./storage", () => ({
  loadSettings: () => mockLoadSettings(),
  saveSettings: (settings: unknown) => mockSaveSettings(settings),
  loadUiPreferences: () => mockLoadUiPreferences(),
  saveUiPreferences: (prefs: unknown) => mockSaveUiPreferences(prefs),
}));

vi.mock("./pages/PapersPage", () => ({ PapersPage: () => <div>Papers</div> }));
vi.mock("./pages/ChatPage", () => ({ ChatPage: () => <div>Chat</div> }));
vi.mock("./pages/ManagementPage", () => ({ ManagementPage: () => <div>Management</div> }));
vi.mock("./pages/SettingsPage", () => ({ SettingsPage: () => <div>Settings</div> }));

import App from "./App";

describe("App theme integration", () => {
  beforeEach(() => {
    mockLoadSettings.mockReset();
    mockSaveSettings.mockReset();
    mockLoadUiPreferences.mockReset();
    mockSaveUiPreferences.mockReset();
    mockLoadSettings.mockReturnValue({
      apiBase: "http://127.0.0.1:8000",
      llmBaseUrl: "",
      llmModel: "",
      llmApiKey: "",
      embedBaseUrl: "",
      embedModel: "",
      embedApiKey: "",
    });
    mockLoadUiPreferences.mockReturnValue({ theme: "light" });
    delete document.documentElement.dataset.theme;
  });

  it("applies persisted theme on mount", async () => {
    render(<App />);

    await waitFor(() => {
      expect(document.documentElement.dataset.theme).toBe("light");
    });
    expect(mockSaveUiPreferences).toHaveBeenCalledWith({ theme: "light" });
  });

  it("updates dataset and persists when toggled", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Dark" }));

    await waitFor(() => {
      expect(document.documentElement.dataset.theme).toBe("dark");
    });
    expect(mockSaveUiPreferences).toHaveBeenLastCalledWith({ theme: "dark" });
  });
});
