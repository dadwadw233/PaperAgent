import React from "react";
import { Settings } from "../types";

interface Props {
  settings: Settings;
  onChange: (settings: Settings) => void;
  onSave: () => void;
  saving: boolean;
  lastSynced?: string | null;
  error?: string | null;
}

export const SettingsPanel: React.FC<Props> = ({ settings, onChange, onSave, saving, lastSynced, error }) => {
  const update = (key: keyof Settings, value: string) => {
    onChange({ ...settings, [key]: value });
  };

  return (
    <div className="panel settings">
      <div className="panel-header">
        <div className="pill">Settings</div>
        <div className="pill info">Editable locally</div>
      </div>
      <div className="settings-row">
        <label htmlFor="apiBase">Backend API base</label>
        <input
          id="apiBase"
          placeholder="http://127.0.0.1:8000"
          value={settings.apiBase}
          onChange={(e) => update("apiBase", e.target.value)}
        />
      </div>
      <div className="settings-row">
        <label htmlFor="llmBase">LLM Base URL (OpenAI compatible)</label>
        <input
          id="llmBase"
          placeholder="https://your-endpoint/v1"
          value={settings.llmBaseUrl}
          onChange={(e) => update("llmBaseUrl", e.target.value)}
        />
      </div>
      <div className="settings-row">
        <label htmlFor="llmModel">LLM Model Name</label>
        <input
          id="llmModel"
          placeholder="gpt-3.5-turbo"
          value={settings.llmModel}
          onChange={(e) => update("llmModel", e.target.value)}
        />
      </div>
      <div className="settings-row">
        <label htmlFor="llmKey">LLM API Key (stored locally)</label>
        <input
          id="llmKey"
          type="password"
          placeholder="sk-..."
          value={settings.llmApiKey}
          onChange={(e) => update("llmApiKey", e.target.value)}
        />
      </div>
      <div className="settings-row">
        <label htmlFor="embedBase">Embedding Base URL (fallback to LLM if empty)</label>
        <input
          id="embedBase"
          placeholder="https://your-endpoint/v1"
          value={settings.embedBaseUrl}
          onChange={(e) => update("embedBaseUrl", e.target.value)}
        />
      </div>
      <div className="settings-row">
        <label htmlFor="embedModel">Embedding Model Name</label>
        <input
          id="embedModel"
          placeholder="text-embedding-3-large"
          value={settings.embedModel}
          onChange={(e) => update("embedModel", e.target.value)}
        />
      </div>
      <div className="settings-row">
        <label htmlFor="embedKey">Embedding API Key</label>
        <input
          id="embedKey"
          type="password"
          placeholder="sk-..."
          value={settings.embedApiKey}
          onChange={(e) => update("embedApiKey", e.target.value)}
        />
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button className="primary-btn" onClick={onSave} disabled={saving}>
          {saving ? "Saving…" : "Save to backend"}
        </button>
        {lastSynced && <span className="muted">Last synced: {lastSynced}</span>}
        {error && <span className="pill warn">{error}</span>}
      </div>
      <div className="muted">Values are kept locally and pushed to backend config when you click save.</div>
    </div>
  );
};
