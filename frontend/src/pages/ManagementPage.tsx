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
          <p className="page-subtitle">Import data and run processing pipelines</p>
        </div>
        <button className="ghost-btn" onClick={loadStats}>
          Refresh
        </button>
      </div>

      <div className="management-layout">
        {/* Statistics Section */}
        <div className="management-section">
          <h2 className="management-section-title">Statistics</h2>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-label">Total Papers</div>
              <div className="stat-value">{loading ? "..." : stats.total.toLocaleString()}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Last Updated</div>
              <div className="stat-value" style={{ fontSize: "18px" }}>
                {stats.lastUpdate || "N/A"}
              </div>
            </div>
          </div>
        </div>

        {/* Import Section */}
        <div className="management-section">
          <h2 className="management-section-title">Import Data</h2>
          <div className="action-grid">
            <div className="action-card">
              <div className="action-card-header">
                <h3 className="action-card-title">CSV Import</h3>
              </div>
              <div className="action-card-body">
                <p className="action-description">
                  Upload a Zotero CSV export file to import papers into the database.
                  The CSV should contain paper metadata including titles, authors, DOIs, and file attachments.
                </p>
                <CsvUploader settings={settings} onUploaded={loadStats} />
              </div>
            </div>
          </div>
        </div>

        {/* Processing Pipeline Section */}
        <div className="management-section">
          <h2 className="management-section-title">Processing Pipeline</h2>
          <div className="action-grid">
            <PipelinePanel settings={settings} onSummaryFinished={loadStats} />
          </div>
        </div>
      </div>
    </div>
  );
};
