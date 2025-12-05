import { Settings } from "./types";

const SETTINGS_KEY = "paper-agent-settings";

export const defaultSettings: Settings = {
  apiBase: import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000",
  llmBaseUrl: "",
  llmModel: "gpt-3.5-turbo",
  llmApiKey: "",
};

export function loadSettings(): Settings {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) {
      return { ...defaultSettings, ...JSON.parse(raw) };
    }
  } catch (err) {
    console.warn("Failed to load settings from localStorage", err);
  }
  return defaultSettings;
}

export function saveSettings(settings: Settings) {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch (err) {
    console.warn("Failed to save settings", err);
  }
}
