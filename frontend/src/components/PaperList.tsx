import React from "react";
import { PaperListItem } from "../types";

interface Props {
  items: PaperListItem[];
  total: number;
  loading: boolean;
  selectedId: number | null;
  onSelect: (id: number) => void;
  onLoadMore?: () => void;
  canLoadMore?: boolean;
  loadingMore?: boolean;
}

export const PaperList: React.FC<Props> = ({
  items,
  total,
  loading,
  selectedId,
  onSelect,
  onLoadMore,
  canLoadMore,
  loadingMore,
}) => {
  return (
    <div className="panel">
      <div className="panel-header">
        <div className="pill info">Total {total}</div>
        {loading && <div className="pill">Loading…</div>}
      </div>
      <div className="list">
        {items.length === 0 && !loading && <div className="empty">No papers found.</div>}
        {items.map((paper) => (
          <div
            key={paper.id}
            className={`card ${paper.id === selectedId ? "active" : ""}`}
            onClick={() => onSelect(paper.id)}
          >
            <div className="card-title">{paper.title || "Untitled"}</div>
            <div className="muted">
              {paper.item_type || "Unknown"} · {paper.year || "—"}
            </div>
            {paper.doi && (
              <div className="muted" title={paper.doi}>
                DOI: {paper.doi}
              </div>
            )}
          </div>
        ))}
      </div>
      {canLoadMore && (
        <div style={{ marginTop: 8 }}>
          <button className="primary-btn" onClick={onLoadMore} disabled={loadingMore}>
            {loadingMore ? "加载中…" : "加载更多"}
          </button>
        </div>
      )}
    </div>
  );
};
