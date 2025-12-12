import React, { useEffect, useState } from "react";
import { SettingsPanel } from "../components/SettingsPanel";
import { Settings } from "../types";
import { fetchConfig, updateConfig } from "../api";
import { defaultSettings } from "../storage";

interface SettingsPageProps {
  settings: Settings;
  onChange: (settings: Settings) => void;
}

export const SettingsPage: React.FC<SettingsPageProps> = ({ settings, onChange }) => {
  const [savingConfig, setSavingConfig] = useState(false);
  const [configError, setConfigError] = useState<string | null>(null);
  const [lastSynced, setLastSynced] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        const cfg = await fetchConfig(settings);
        onChange({
          ...settings,
          llmBaseUrl: cfg.LLM_BASE_URL || settings.llmBaseUrl,
          llmModel: cfg.LLM_MODEL || settings.llmModel,
          llmApiKey: cfg.LLM_API_KEY || settings.llmApiKey,
          embedBaseUrl: cfg.EMBED_BASE_URL || cfg.LLM_BASE_URL || settings.embedBaseUrl,
          embedModel: cfg.EMBED_MODEL || settings.embedModel || cfg.LLM_MODEL || settings.llmModel,
          embedApiKey: cfg.EMBED_API_KEY || cfg.LLM_API_KEY || settings.embedApiKey,
        });
        setLastSynced(new Date().toLocaleString());
        setConfigError(null);
      } catch (err) {
        setConfigError(err instanceof Error ? err.message : "Load config failed");
      }
    };
    loadConfig();
  }, [settings.apiBase]);

  const saveConfigToBackend = async () => {
    setSavingConfig(true);
    setConfigError(null);
    setSuccessMessage(null);
    try {
      await updateConfig(settings, {
        LLM_BASE_URL: settings.llmBaseUrl,
        LLM_MODEL: settings.llmModel,
        LLM_API_KEY: settings.llmApiKey,
        EMBED_BASE_URL: settings.embedBaseUrl || settings.llmBaseUrl,
        EMBED_MODEL: settings.embedModel || settings.llmModel,
        EMBED_API_KEY: settings.embedApiKey || settings.llmApiKey,
      });
      setLastSynced(new Date().toLocaleString());
      setSuccessMessage("Settings saved successfully!");
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err) {
      setConfigError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSavingConfig(false);
    }
  };

  const resetToDefaults = () => {
    if (confirm("Are you sure you want to reset all settings to defaults?")) {
      onChange(defaultSettings);
      setSuccessMessage("Settings reset to defaults");
      setTimeout(() => setSuccessMessage(null), 3000);
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-subtitle">Configure API endpoints and model parameters</p>
        </div>
        <button className="ghost-btn" onClick={resetToDefaults}>
          🔄 Reset to Defaults
        </button>
      </div>

      {successMessage && (
        <div className="success-banner">
          ✅ {successMessage}
        </div>
      )}

      <div className="settings-layout">
        <div className="panel settings-main-panel">
          <SettingsPanel
            settings={settings}
            onChange={onChange}
            onSave={saveConfigToBackend}
            saving={savingConfig}
            lastSynced={lastSynced}
            error={configError}
          />
        </div>

        <div className="panel settings-info-panel">
          <div className="panel-header">
            <h3>ℹ️ About Settings</h3>
          </div>
          <div className="info-content">
            <div className="info-section">
              <h4>API Base URL</h4>
              <p>The backend API endpoint for Paper Agent</p>
            </div>
            <div className="info-section">
              <h4>LLM Configuration</h4>
              <p>Configure the language model for chat and summarization features</p>
            </div>
            <div className="info-section">
              <h4>Embedding Model</h4>
              <p>Configure the embedding model for vector search capabilities</p>
            </div>
            <div className="info-section">
              <h4>Storage</h4>
              <p>Settings are stored locally in your browser and synced with the backend</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

