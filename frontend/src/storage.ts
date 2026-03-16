import { ChatMessage, ChatRole, ChatSession, ChatSessionStore, Settings, ThemeMode } from "./types";

const SETTINGS_KEY = "paper-agent-settings";
const UI_PREFERENCES_KEY = "paper-agent-ui-preferences";
const CHAT_SESSIONS_KEY = "paper-agent-chat-sessions";
const ENV_API_BASE = import.meta.env.VITE_API_BASE as string | undefined;
const MAX_CHAT_SESSIONS = 50;
const MAX_SESSION_MESSAGES = 120;

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

export interface UiPreferences {
  theme: ThemeMode;
}

export const defaultUiPreferences: UiPreferences = {
  theme: "dark",
};

function makeSessionId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `session-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

function normalizeRole(value: unknown): ChatRole | null {
  if (value === "user" || value === "assistant" || value === "system") {
    return value;
  }
  return null;
}

function normalizeMessage(value: unknown): ChatMessage | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const row = value as Record<string, unknown>;
  const role = normalizeRole(row.role);
  const content = typeof row.content === "string" ? row.content : "";
  if (!role || !content.trim()) {
    return null;
  }
  return {
    role,
    content,
    citations: Array.isArray(row.citations) ? (row.citations as ChatMessage["citations"]) : undefined,
    retrievalMeta:
      row.retrievalMeta && typeof row.retrievalMeta === "object"
        ? (row.retrievalMeta as ChatMessage["retrievalMeta"])
        : undefined,
  };
}

function cleanIso(value: unknown, fallback: string): string {
  if (typeof value !== "string" || !value.trim()) {
    return fallback;
  }
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return fallback;
  }
  return new Date(timestamp).toISOString();
}

function normalizeSession(value: unknown): ChatSession | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const row = value as Record<string, unknown>;
  const id = typeof row.id === "string" && row.id.trim() ? row.id : makeSessionId();
  const nowIso = new Date().toISOString();
  const createdAt = cleanIso(row.createdAt, nowIso);
  const updatedAt = cleanIso(row.updatedAt, createdAt);
  const title = typeof row.title === "string" && row.title.trim() ? row.title.trim() : "New session";
  const rawMessages = Array.isArray(row.messages) ? row.messages : [];
  const messages = rawMessages.map((item) => normalizeMessage(item)).filter((item): item is ChatMessage => Boolean(item));
  return {
    id,
    title,
    createdAt,
    updatedAt,
    messages: messages.slice(-MAX_SESSION_MESSAGES),
  };
}

export function createChatSession(now = new Date()): ChatSession {
  const nowIso = now.toISOString();
  return {
    id: makeSessionId(),
    title: "New session",
    createdAt: nowIso,
    updatedAt: nowIso,
    messages: [],
  };
}

export function deriveChatSessionTitle(messages: ChatMessage[], fallbackTitle = "New session"): string {
  const firstUserMessage = messages.find((message) => message.role === "user" && message.content.trim());
  if (!firstUserMessage) {
    return fallbackTitle;
  }
  const normalized = firstUserMessage.content.replace(/\s+/g, " ").trim();
  if (normalized.length <= 42) {
    return normalized;
  }
  return `${normalized.slice(0, 42).trimEnd()}...`;
}

function ensureChatStore(raw: Partial<ChatSessionStore> | null | undefined): ChatSessionStore {
  const parsedSessions = Array.isArray(raw?.sessions)
    ? raw.sessions.map((item) => normalizeSession(item)).filter((item): item is ChatSession => Boolean(item))
    : [];
  const sessions = parsedSessions.slice(0, MAX_CHAT_SESSIONS);
  if (sessions.length === 0) {
    const fallback = createChatSession();
    return {
      activeSessionId: fallback.id,
      sessions: [fallback],
    };
  }
  const requestedActive = typeof raw?.activeSessionId === "string" ? raw.activeSessionId : "";
  const hasActive = sessions.some((session) => session.id === requestedActive);
  return {
    activeSessionId: hasActive ? requestedActive : sessions[0].id,
    sessions,
  };
}

export function loadChatSessionStore(): ChatSessionStore {
  try {
    const raw = localStorage.getItem(CHAT_SESSIONS_KEY);
    if (!raw) {
      return ensureChatStore(null);
    }
    const parsed = JSON.parse(raw) as Partial<ChatSessionStore>;
    return ensureChatStore(parsed);
  } catch (err) {
    console.warn("Failed to load chat sessions from localStorage", err);
    return ensureChatStore(null);
  }
}

export function saveChatSessionStore(store: ChatSessionStore) {
  try {
    const normalized = ensureChatStore(store);
    localStorage.setItem(CHAT_SESSIONS_KEY, JSON.stringify(normalized));
  } catch (err) {
    console.warn("Failed to save chat sessions", err);
  }
}

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

function isThemeMode(value: unknown): value is ThemeMode {
  return value === "dark" || value === "light";
}

export function loadUiPreferences(): UiPreferences {
  try {
    const raw = localStorage.getItem(UI_PREFERENCES_KEY);
    if (!raw) {
      return defaultUiPreferences;
    }
    const parsed = JSON.parse(raw) as Partial<UiPreferences>;
    const theme = isThemeMode(parsed.theme) ? parsed.theme : defaultUiPreferences.theme;
    return { theme };
  } catch (err) {
    console.warn("Failed to load UI preferences from localStorage", err);
    return defaultUiPreferences;
  }
}

export function saveUiPreferences(prefs: UiPreferences) {
  try {
    localStorage.setItem(UI_PREFERENCES_KEY, JSON.stringify(prefs));
  } catch (err) {
    console.warn("Failed to save UI preferences", err);
  }
}
