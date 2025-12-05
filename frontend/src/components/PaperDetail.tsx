import React from "react";
import { clearSummary } from "../api";
import { PaperDetail as PaperDetailData, Settings } from "../types";

interface Props {
  detail: PaperDetailData | null;
  loading: boolean;
  error?: string | null;
  settings: Settings;
  onCleared: () => void;
}

export const PaperDetailPanel: React.FC<Props> = ({ detail, loading, error, settings, onCleared }) => {
  if (loading) {
    return (
      <div className="panel detail">
        <div className="pill">Loading paper…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="panel detail">
        <div className="pill warn">{error}</div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="panel detail">
        <div className="empty">Select a paper to see details.</div>
      </div>
    );
  }

  const hasSummary =
    detail.summary?.long_summary || detail.summary?.one_liner || detail.summary?.snarky_comment;

  const handleClear = async () => {
    if (!detail) return;
    try {
      await clearSummary(settings, detail.id);
      onCleared();
    } catch (err) {
      alert(err instanceof Error ? err.message : "清除失败");
    }
  };

  return (
    <div className="panel detail">
      <div className="panel-header">
        <div>
          <div className="pill">{detail.item_type || "Paper"}</div>
        </div>
        {detail.year && <div className="pill info">{detail.year}</div>}
      </div>
      <div>
        <h2 style={{ margin: "4px 0 6px 0" }}>{detail.title || "Untitled"}</h2>
        <div className="muted">{detail.authors || "Unknown authors"}</div>
        {detail.url && (
          <div style={{ marginTop: 6 }}>
            <a href={detail.url} target="_blank" rel="noreferrer" className="pill info">
              Open source
            </a>
          </div>
        )}
      </div>

      {detail.abstract && (
        <div className="summary-block">
          <h4>Abstract</h4>
          <div>{detail.abstract}</div>
        </div>
      )}

      {hasSummary ? (
        <>
          {detail.summary?.one_liner && (
            <div className="summary-block">
              <h4>One Liner</h4>
              <div>{detail.summary.one_liner}</div>
            </div>
          )}
          {detail.summary?.long_summary && (
            <div className="summary-block">
              <h4>Full Summary</h4>
              <div>{detail.summary.long_summary}</div>
            </div>
          )}
          {detail.summary?.snarky_comment && (
            <div className="summary-block">
              <h4>Snarky Comment</h4>
              <div>{detail.summary.snarky_comment}</div>
            </div>
          )}
        </>
      ) : (
        <div className="summary-block">
          <h4>AI Summary</h4>
          <div className="muted">Not generated yet. Run summarize script.</div>
        </div>
      )}

      {hasSummary && (
        <div>
          <button className="ghost-btn" onClick={handleClear}>
            清除 AI 摘要/标签
          </button>
        </div>
      )}

      <div className="summary-block">
        <h4>Tags</h4>
        <div className="tag-row">
          {detail.tags.length === 0 && <span className="muted">No tags yet.</span>}
          {detail.tags.map((tag) => (
            <span key={`${tag.type}-${tag.value}`} className="pill">
              {tag.type}: {tag.value}
            </span>
          ))}
        </div>
      </div>

      {detail.attachments.length > 0 && (
        <div className="summary-block">
          <h4>Attachments</h4>
          <div className="tag-row">
            {detail.attachments.map((att) => (
              <span key={att.path} className="pill">
                {att.type || "file"} · {att.path}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
