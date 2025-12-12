import React, { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Layout } from "./components/Layout";
import { PapersPage } from "./pages/PapersPage";
import { ChatPage } from "./pages/ChatPage";
import { ManagementPage } from "./pages/ManagementPage";
import { SettingsPage } from "./pages/SettingsPage";
import { loadSettings, saveSettings } from "./storage";
import { Settings } from "./types";

const App: React.FC = () => {
  const [settings, setSettings] = useState<Settings>(() => loadSettings());

  useEffect(() => {
    saveSettings(settings);
  }, [settings]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<PapersPage settings={settings} />} />
          <Route path="chat" element={<ChatPage settings={settings} />} />
          <Route path="management" element={<ManagementPage settings={settings} />} />
          <Route path="settings" element={<SettingsPage settings={settings} onChange={setSettings} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
