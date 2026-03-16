import React, { useMemo, useState } from "react";
import { chatWithPaper, chatWithPaperStream } from "../api";
import { ChatCitation, ChatRetrievalMeta, PaperDetail, Settings } from "../types";

interface Props {
  paper: PaperDetail | null;
  settings: Settings;
  onJumpToPaper?: (paperId: number) => void;
}

interface Message {
  role: "user" | "assistant" | "system";
  content: string;
  citations?: ChatCitation[];
  retrievalMeta?: ChatRetrievalMeta | null;
}

export const ChatPanel: React.FC<Props> = ({ paper, settings, onJumpToPaper }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [scope, setScope] = useState<"library" | "paper">("library");
  const [usePaperFilter, setUsePaperFilter] = useState(false);
  const [candidateK, setCandidateK] = useState(20);
  const [finalK, setFinalK] = useState(6);
  const [rerank, setRerank] = useState(true);
  const [requireCitations, setRequireCitations] = useState(true);
  const [showDebug, setShowDebug] = useState(false);
  const [debugSendFullText, setDebugSendFullText] = useState(false);

  const candidateKMin = finalK;
  const canUsePaperMode = Boolean(paper?.id);
  const effectivePaperId = useMemo(() => {
    if (scope === "paper") {
      return paper?.id;
    }
    if (usePaperFilter) {
      return paper?.id;
    }
    return undefined;
  }, [scope, usePaperFilter, paper?.id]);

  const send = async () => {
    if (!input.trim()) return;
    if (scope === "paper" && !paper?.id) {
      setError("Paper mode requires selecting a paper.");
      return;
    }
    if (debugSendFullText && !paper?.id) {
      setError("Debug full-text mode requires selecting a paper.");
      return;
    }
    setError(null);
    const prompt = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: prompt }, { role: "assistant", content: "" }]);
    setLoading(true);
    const replaceLatestAssistant = (
      content: string,
      payload?: { citations?: ChatCitation[]; retrievalMeta?: ChatRetrievalMeta | null },
    ) => {
      setMessages((prev) => {
        const next = [...prev];
        for (let i = next.length - 1; i >= 0; i -= 1) {
          if (next[i].role === "assistant") {
            next[i] = {
              ...next[i],
              content,
              citations: payload?.citations ?? next[i].citations,
              retrievalMeta: payload?.retrievalMeta ?? next[i].retrievalMeta ?? null,
            };
            break;
          }
        }
        return next;
      });
    };
    const appendAssistantDelta = (delta: string) => {
      if (!delta) return;
      setMessages((prev) => {
        const next = [...prev];
        for (let i = next.length - 1; i >= 0; i -= 1) {
          if (next[i].role === "assistant") {
            next[i] = { ...next[i], content: `${next[i].content || ""}${delta}` };
            break;
          }
        }
        return next;
      });
    };
    const dropEmptyAssistant = () => {
      setMessages((prev) => {
        if (prev.length === 0) return prev;
        const last = prev[prev.length - 1];
        if (last.role === "assistant" && !last.content.trim()) {
          return prev.slice(0, -1);
        }
        return prev;
      });
    };

    let streamedChars = 0;
    try {
      const payload = {
        query: prompt,
        scope: debugSendFullText ? "paper" : scope,
        paper_id: debugSendFullText ? paper?.id : effectivePaperId,
        candidate_k: Math.max(candidateK, finalK),
        final_k: finalK,
        rerank,
        require_citations: requireCitations,
        send_full_text: showDebug && debugSendFullText ? true : undefined,
      };
      const resp = await chatWithPaperStream(settings, payload, {
        onDelta: (delta) => {
          streamedChars += delta.length;
          appendAssistantDelta(delta);
        },
        onFinal: (finalPayload) => {
          replaceLatestAssistant(finalPayload.answer || "", {
            citations: finalPayload.citations || [],
            retrievalMeta: finalPayload.retrieval_meta || null,
          });
        },
      });
      replaceLatestAssistant(resp.answer || "", {
        citations: resp.citations || [],
        retrievalMeta: resp.retrieval_meta || null,
      });
    } catch (err) {
      if (streamedChars === 0) {
        try {
          const fallback = await chatWithPaper(settings, {
            query: prompt,
            scope: debugSendFullText ? "paper" : scope,
            paper_id: debugSendFullText ? paper?.id : effectivePaperId,
            candidate_k: Math.max(candidateK, finalK),
            final_k: finalK,
            rerank,
            require_citations: requireCitations,
            send_full_text: showDebug && debugSendFullText ? true : undefined,
          });
          replaceLatestAssistant(fallback.answer || "", {
            citations: fallback.citations || [],
            retrievalMeta: fallback.retrieval_meta || null,
          });
        } catch (fallbackErr) {
          dropEmptyAssistant();
          setError(fallbackErr instanceof Error ? fallbackErr.message : "Chat failed");
        }
      } else {
        setError(err instanceof Error ? err.message : "Chat stream failed");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat">
      <div className="chat-header">
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className="chat-title">Conversation</span>
          {loading && <span className="pill info">Processing...</span>}
          <span className="pill info">Default: Library RAG</span>
          {paper?.id ? (
            <span className="pill">Selected paper #{paper.id}</span>
          ) : (
            <span className="pill">No paper selected</span>
          )}
        </div>
      </div>

      <div className="chat-options">
        <label className="checkbox-label">
          <input
            type="radio"
            checked={scope === "library"}
            onChange={() => setScope("library")}
            disabled={loading}
          />
          <span>Library scope</span>
        </label>
        <label className="checkbox-label">
          <input
            type="radio"
            checked={scope === "paper"}
            onChange={() => setScope("paper")}
            disabled={!canUsePaperMode || loading}
          />
          <span>Current paper only</span>
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={usePaperFilter}
            onChange={(e) => setUsePaperFilter(e.target.checked)}
            disabled={!canUsePaperMode || scope === "paper" || loading}
          />
          <span>Filter library by selected paper</span>
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={rerank}
            onChange={(e) => setRerank(e.target.checked)}
            disabled={loading}
          />
          <span>Enable rerank</span>
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={requireCitations}
            onChange={(e) => setRequireCitations(e.target.checked)}
            disabled={loading}
          />
          <span>Require citations</span>
        </label>
      </div>

      <div className="chat-options" style={{ borderTop: "1px solid var(--border)" }}>
        <label style={{ display: "flex", alignItems: "center", gap: "8px", width: "50%" }}>
          <span style={{ minWidth: "120px" }}>Candidate K: {candidateK}</span>
          <input
            type="range"
            min={candidateKMin}
            max={50}
            value={candidateK}
            onChange={(e) => setCandidateK(Number(e.target.value))}
            disabled={loading}
            style={{ flex: 1 }}
          />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: "8px", width: "50%" }}>
          <span style={{ minWidth: "90px" }}>Final K: {finalK}</span>
          <input
            type="range"
            min={1}
            max={12}
            value={finalK}
            onChange={(e) => {
              const next = Number(e.target.value);
              setFinalK(next);
              if (candidateK < next) {
                setCandidateK(next);
              }
            }}
            disabled={loading}
            style={{ flex: 1 }}
          />
        </label>
      </div>

      <div className="chat-options" style={{ borderTop: "1px solid var(--border)" }}>
        <button className="ghost-btn" onClick={() => setShowDebug((prev) => !prev)} disabled={loading}>
          {showDebug ? "Hide debug options" : "Show debug options"}
        </button>
        {showDebug && (
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={debugSendFullText}
              onChange={(e) => setDebugSendFullText(e.target.checked)}
              disabled={loading}
            />
            <span>Debug: send full text (legacy)</span>
          </label>
        )}
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-row">
            <div className="role">system</div>
            <div className="bubble">
              Ask questions directly in library mode, or select a paper and switch to paper mode.
              <br />
              <span className="muted">Answers are grounded with citations by default.</span>
            </div>
          </div>
        )}
        {messages.map((m, idx) => (
          <div className="chat-row" key={idx}>
            <div className="role">{m.role}</div>
            <div className="bubble">{m.content}</div>
            {m.role === "assistant" && (m.citations?.length || 0) > 0 && (
              <details className="assistant-source-details">
                {(() => {
                  const paperMap = new Map<number, { paperId: number; title: string }>();
                  (m.citations || []).forEach((citation) => {
                    if (citation.paper_id == null || paperMap.has(citation.paper_id)) return;
                    paperMap.set(citation.paper_id, {
                      paperId: citation.paper_id,
                      title: citation.paper_title?.trim() || `Paper #${citation.paper_id}`,
                    });
                  });
                  const papers = Array.from(paperMap.values());
                  return (
                    <>
                      <summary>Sources ({papers.length} papers)</summary>
                      <div className="assistant-source-body">
                        {papers.map((paperSource) => (
                          <div key={paperSource.paperId} className="assistant-source-item">
                            <div className="assistant-source-text">
                              <span className="assistant-source-id">#{paperSource.paperId}</span>
                              <span className="assistant-source-title">{paperSource.title}</span>
                            </div>
                            {onJumpToPaper && (
                              <button
                                className="ghost-btn"
                                onClick={() => onJumpToPaper(paperSource.paperId)}
                              >
                                Open
                              </button>
                            )}
                          </div>
                        ))}
                        {m.retrievalMeta && (
                          <div className="assistant-source-meta">
                            retrieval {m.retrievalMeta.timings_ms.retrieval}ms · generation{" "}
                            {m.retrievalMeta.timings_ms.generation}ms
                          </div>
                        )}
                      </div>
                    </>
                  );
                })()}
              </details>
            )}
          </div>
        ))}
        {error && (
          <div className="chat-row">
            <div className="role">error</div>
            <div className="bubble error">{error}</div>
          </div>
        )}
      </div>

      <div className="chat-input">
        <textarea
          placeholder="Ask a question about your papers..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          disabled={loading}
        />
        <button className="primary-btn" onClick={send} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
};
