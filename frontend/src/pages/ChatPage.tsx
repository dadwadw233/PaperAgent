import React, { useEffect, useState } from "react";
import { fetchPapers } from "../api";
import { ChatPanel } from "../components/ChatPanel";
import { PaperListItem, Settings } from "../types";

interface ChatPageProps {
  settings: Settings;
}

export const ChatPage: React.FC<ChatPageProps> = ({ settings }) => {
  const [papers, setPapers] = useState<PaperListItem[]>([]);
  const [selectedPaperId, setSelectedPaperId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadRecentPapers();
  }, [settings.apiBase]);

  const loadRecentPapers = async () => {
    setLoading(true);
    try {
      const resp = await fetchPapers(settings, { limit: 50, offset: 0 });
      setPapers(resp.items);
    } catch (err) {
      console.error("Failed to load papers:", err);
    } finally {
      setLoading(false);
    }
  };

  const filteredPapers = papers.filter((p) =>
    searchQuery ? p.title?.toLowerCase().includes(searchQuery.toLowerCase()) : true
  );

  const selectedPaper = selectedPaperId ? papers.find((p) => p.id === selectedPaperId) : null;

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Chat with Papers</h1>
          <p className="page-subtitle">Ask questions about your paper collection</p>
        </div>
      </div>

      <div className="chat-layout">
        <div className="chat-sidebar-section">
          <div className="panel">
            <div className="panel-header">
              <h3>Select Paper (Optional)</h3>
            </div>
            
            <input
              type="text"
              className="search-input"
              placeholder="Search papers..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ marginBottom: 12 }}
            />

            {selectedPaperId && (
              <button
                className="ghost-btn"
                style={{ width: "100%", marginBottom: 12 }}
                onClick={() => setSelectedPaperId(null)}
              >
                Clear Selection
              </button>
            )}

            <div className="paper-select-list">
              {loading && <div className="empty">Loading papers...</div>}
              {!loading && filteredPapers.length === 0 && (
                <div className="empty">No papers found</div>
              )}
              {filteredPapers.map((paper) => (
                <div
                  key={paper.id}
                  className={`card compact ${selectedPaperId === paper.id ? "active" : ""}`}
                  onClick={() => setSelectedPaperId(paper.id)}
                >
                  <div className="card-title" style={{ fontSize: 14 }}>
                    {paper.title || "Untitled"}
                  </div>
                  <div className="muted">
                    {paper.year ? `Year: ${paper.year}` : "Year: N/A"}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="chat-main-section">
          <div className="panel" style={{ height: "100%" }}>
            <ChatPanel
              paper={selectedPaper ? {
                ...selectedPaper,
                authors: null,
                abstract: null,
                manual_tags: null,
                automatic_tags: null,
                summary: null,
                tags: [],
                attachments: []
              } : null}
              settings={settings}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

