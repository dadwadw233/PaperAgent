import React, { useEffect, useState, useRef, useCallback } from "react";
import { fetchPapers } from "../api";
import { ChatPanel } from "../components/ChatPanel";
import { PaperListItem, Settings } from "../types";

interface ChatPageProps {
  settings: Settings;
}

export const ChatPage: React.FC<ChatPageProps> = ({ settings }) => {
  const [papers, setPapers] = useState<PaperListItem[]>([]);
  const [allPapers, setAllPapers] = useState<PaperListItem[]>([]);
  const [selectedPaperId, setSelectedPaperId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [offset, setOffset] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);
  const LIMIT = 100;

  useEffect(() => {
    loadInitialPapers();
  }, [settings.apiBase]);

  const loadInitialPapers = async () => {
    setLoading(true);
    try {
      const resp = await fetchPapers(settings, { limit: LIMIT, offset: 0 });
      setAllPapers(resp.items);
      setPapers(resp.items);
      setOffset(LIMIT);
      setHasMore(resp.items.length === LIMIT);
    } catch (err) {
      console.error("Failed to load papers:", err);
    } finally {
      setLoading(false);
    }
  };

  const loadMorePapers = async () => {
    if (loading || !hasMore) return;
    setLoading(true);
    try {
      const resp = await fetchPapers(settings, { limit: LIMIT, offset });
      setAllPapers(prev => [...prev, ...resp.items]);
      if (!searchQuery) {
        setPapers(prev => [...prev, ...resp.items]);
      }
      setOffset(prev => prev + LIMIT);
      setHasMore(resp.items.length === LIMIT);
    } catch (err) {
      console.error("Failed to load more papers:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleScroll = useCallback(() => {
    if (!listRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = listRef.current;
    if (scrollHeight - scrollTop - clientHeight < 100 && hasMore && !loading) {
      loadMorePapers();
    }
  }, [hasMore, loading]);

  useEffect(() => {
    const list = listRef.current;
    if (list) {
      list.addEventListener('scroll', handleScroll);
      return () => list.removeEventListener('scroll', handleScroll);
    }
  }, [handleScroll]);

  // Enhanced search: title, authors, DOI, abstract
  useEffect(() => {
    if (!searchQuery.trim()) {
      setPapers(allPapers);
      return;
    }

    const query = searchQuery.toLowerCase();
    const filtered = allPapers.filter((p) => {
      return (
        p.title?.toLowerCase().includes(query) ||
        p.doi?.toLowerCase().includes(query) ||
        p.key?.toLowerCase().includes(query)
      );
    });
    setPapers(filtered);
  }, [searchQuery, allPapers]);

  const selectedPaper = selectedPaperId ? allPapers.find((p) => p.id === selectedPaperId) : null;

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Chat with Papers</h1>
          <p className="page-subtitle">
            {searchQuery ? `${papers.length} papers found` : `${allPapers.length} papers loaded`}
          </p>
        </div>
      </div>

      <div className="chat-layout">
        <div className="chat-sidebar-section">
          <div className="panel">
            <div className="panel-header">
              <h3>Select Paper</h3>
            </div>
            
            <div className="search-box-wrapper">
              <svg className="search-icon" width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M7 13C10.3137 13 13 10.3137 13 7C13 3.68629 10.3137 1 7 1C3.68629 1 1 3.68629 1 7C1 10.3137 3.68629 13 7 13Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                <path d="M11.5 11.5L15 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
              <input
                type="text"
                className="search-box"
                placeholder="Search by title, DOI, or key..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button className="clear-btn" onClick={() => setSearchQuery("")}>
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M1 1L13 13M1 13L13 1" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                  </svg>
                </button>
              )}
            </div>

            {selectedPaperId && (
              <button
                className="ghost-btn"
                style={{ width: "100%", marginBottom: 12 }}
                onClick={() => setSelectedPaperId(null)}
              >
                Clear Selection
              </button>
            )}

            <div className="paper-select-list" ref={listRef}>
              {loading && papers.length === 0 && <div className="empty">Loading papers...</div>}
              {!loading && papers.length === 0 && (
                <div className="empty">No papers found</div>
              )}
              {papers.map((paper, idx) => (
                <div
                  key={paper.id}
                  className={`card compact ${selectedPaperId === paper.id ? "active" : ""}`}
                  onClick={() => setSelectedPaperId(paper.id)}
                  style={{ animationDelay: `${Math.min(idx * 0.03, 0.3)}s` }}
                >
                  <div className="card-title" style={{ fontSize: 14 }}>
                    {paper.title || "Untitled"}
                  </div>
                  <div className="muted">
                    {paper.year ? `Year: ${paper.year}` : "Year: N/A"}
                  </div>
                </div>
              ))}
              {loading && papers.length > 0 && (
                <div className="loading-more">Loading more...</div>
              )}
            </div>
          </div>
        </div>

        <div className="chat-main-section">
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
  );
};
