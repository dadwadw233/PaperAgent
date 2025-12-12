import { Settings } from "./types";

const SETTINGS_KEY = "paper-agent-settings";
const ENV_API_BASE = import.meta.env.VITE_API_BASE as string | undefined;

function resolveDefaultApiBase(): string {
  const envBase = ENV_API_BASE;
  if (envBase) {
    return envBase;
  }
  if (typeof window !== "undefined" && window.location) {
    const protocol = window.location.protocol || "http:";
    const hostname = window.location.hostname || "127.0.0.1";
    return `${protocol}//${hostname}:8000`;
  }
  return "http://127.0.0.1:8000";
}

export const defaultSettings: Settings = {
  apiBase: resolveDefaultApiBase(),
  llmBaseUrl: "",
  llmModel: "gpt-3.5-turbo",
  llmApiKey: "",
  embedBaseUrl: "",
  embedModel: "",
  embedApiKey: "",
};

export function loadSettings(): Settings {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) {
      const parsed = { ...defaultSettings, ...JSON.parse(raw) } as Settings;
      if (ENV_API_BASE) {
        parsed.apiBase = ENV_API_BASE;
      }
      return parsed;
    }
  } catch (err) {
    console.warn("Failed to load settings from localStorage", err);
  }
  if (ENV_API_BASE) {
    return { ...defaultSettings, apiBase: ENV_API_BASE };
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
