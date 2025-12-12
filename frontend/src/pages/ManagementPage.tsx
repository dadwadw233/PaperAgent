import React, { useEffect, useState } from "react";
import { CsvUploader } from "../components/CsvUploader";
import { PipelinePanel } from "../components/PipelinePanel";
import { Settings } from "../types";
import { fetchPapers } from "../api";

interface ManagementPageProps {
  settings: Settings;
}

export const ManagementPage: React.FC<ManagementPageProps> = ({ settings }) => {
  const [stats, setStats] = useState({ total: 0, lastUpdate: "" });
  const [loading, setLoading] = useState(false);

  const loadStats = async () => {
    setLoading(true);
    try {
      const resp = await fetchPapers(settings, { limit: 1, offset: 0 });
      setStats({
        total: resp.total,
        lastUpdate: new Date().toLocaleString(),
      });
    } catch (err) {
      console.error("Failed to load stats:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStats();
  }, [settings.apiBase]);

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Data Management</h1>
          <p className="page-subtitle">Import, process, and manage your paper collection</p>
        </div>
      </div>

      <div className="management-grid">
        <div className="panel stats-panel">
          <div className="panel-header">
            <h3>📊 Statistics</h3>
          </div>
          <div className="stats-content">
            <div className="stat-item">
              <div className="stat-value">{loading ? "..." : stats.total}</div>
              <div className="stat-label">Total Papers</div>
            </div>
            <div className="stat-item">
              <div className="stat-value">{stats.lastUpdate || "N/A"}</div>
              <div className="stat-label">Last Updated</div>
            </div>
          </div>
          <button className="ghost-btn" onClick={loadStats} style={{ width: "100%", marginTop: 12 }}>
            🔄 Refresh Stats
          </button>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h3>📥 Import Data</h3>
          </div>
          <CsvUploader settings={settings} onUploaded={loadStats} />
        </div>

        <div className="panel pipeline-panel">
          <div className="panel-header">
            <h3>⚡ Processing Pipeline</h3>
          </div>
          <PipelinePanel settings={settings} onSummaryFinished={loadStats} />
        </div>
      </div>
    </div>
  );
};

