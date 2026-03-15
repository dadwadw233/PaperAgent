import React from "react";
import { NavLink, Outlet } from "react-router-dom";
import { ThemeMode } from "../types";

interface Props {
  theme: ThemeMode;
  onThemeChange: (theme: ThemeMode) => void;
}

export const Layout: React.FC<Props> = ({ theme, onThemeChange }) => {
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1 className="app-title">Paper Agent</h1>
        </div>
        
        <nav className="nav">
          <NavLink to="/" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <span>Papers</span>
          </NavLink>
          
          <NavLink to="/chat" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <span>Chat</span>
          </NavLink>
          
          <NavLink to="/management" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <span>Management</span>
          </NavLink>
          
          <NavLink to="/settings" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <span>Settings</span>
          </NavLink>
        </nav>
        
        <div className="sidebar-footer">
          <div className="version">v0.1.0</div>
        </div>
      </aside>

      <main className="main-content">
        <header className="global-toolbar" role="toolbar" aria-label="Global controls">
          <div className="theme-toggle" role="group" aria-label="Theme switcher">
            <button
              className={`theme-toggle-btn ${theme === "light" ? "active" : ""}`}
              onClick={() => onThemeChange("light")}
              aria-pressed={theme === "light"}
            >
              Light
            </button>
            <button
              className={`theme-toggle-btn ${theme === "dark" ? "active" : ""}`}
              onClick={() => onThemeChange("dark")}
              aria-pressed={theme === "dark"}
            >
              Dark
            </button>
          </div>
        </header>
        <Outlet />
      </main>
    </div>
  );
};
