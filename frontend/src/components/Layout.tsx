import React from "react";
import { NavLink, Outlet } from "react-router-dom";

export const Layout: React.FC = () => {
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
        <Outlet />
      </main>
    </div>
  );
};

