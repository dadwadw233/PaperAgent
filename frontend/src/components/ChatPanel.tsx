import React, { useCallback, useEffect, useMemo, useState } from "react";
import { chatWithPaper, chatWithPaperStream } from "../api";
import { createChatSession, deriveChatSessionTitle, loadChatSessionStore, saveChatSessionStore } from "../storage";
import { ChatCitation, ChatMessage, ChatRetrievalMeta, ChatSessionStore, ChatToolCallEvent, PaperDetail, Settings } from "../types";

interface Props {
  paper: PaperDetail | null;
  settings: Settings;
  onJumpToPaper?: (paperId: number) => void;
}

export const ChatPanel: React.FC<Props> = ({ paper, settings, onJumpToPaper }) => {
  const MAX_HISTORY_TURNS = 128;
  const [sessionStore, setSessionStore] = useState<ChatSessionStore>(() => loadChatSessionStore());
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

  const normalizeSessionStore = useCallback((store: ChatSessionStore): ChatSessionStore => {
    if (!Array.isArray(store.sessions) || store.sessions.length === 0) {
      const fallback = createChatSession();
      return { activeSessionId: fallback.id, sessions: [fallback] };
    }
    if (!store.sessions.some((session) => session.id === store.activeSessionId)) {
      return {
        ...store,
        activeSessionId: store.sessions[0].id,
      };
    }
    return store;
  }, []);

  const updateSessionStore = useCallback(
    (updater: (prev: ChatSessionStore) => ChatSessionStore) => {
      setSessionStore((prev) => normalizeSessionStore(updater(normalizeSessionStore(prev))));
    },
    [normalizeSessionStore],
  );

  const activeSession = useMemo(
    () => sessionStore.sessions.find((session) => session.id === sessionStore.activeSessionId) ?? sessionStore.sessions[0],
    [sessionStore],
  );
  const activeSessionId = activeSession?.id;
  const messages = activeSession?.messages || [];

  useEffect(() => {
    saveChatSessionStore(normalizeSessionStore(sessionStore));
  }, [normalizeSessionStore, sessionStore]);

  const updateMessagesForSession = useCallback(
    (
      sessionId: string,
      updater: (previous: ChatMessage[]) => ChatMessage[],
    ) => {
      updateSessionStore((prev) => ({
        ...prev,
        sessions: prev.sessions.map((session) => {
          if (session.id !== sessionId) {
            return session;
          }
          const nextMessages = updater(session.messages);
          return {
            ...session,
            messages: nextMessages,
            title: deriveChatSessionTitle(nextMessages),
            updatedAt: new Date().toISOString(),
          };
        }),
      }));
    },
    [updateSessionStore],
  );

  const createNewSession = () => {
    if (loading) return;
    const nextSession = createChatSession();
    updateSessionStore((prev) => ({
      activeSessionId: nextSession.id,
      sessions: [nextSession, ...prev.sessions].slice(0, 50),
    }));
    setInput("");
    setError(null);
  };

  const deleteCurrentSession = () => {
    if (loading || !activeSessionId) return;
    updateSessionStore((prev) => {
      const remaining = prev.sessions.filter((session) => session.id !== activeSessionId);
      if (remaining.length === 0) {
        const fallback = createChatSession();
        return {
          activeSessionId: fallback.id,
          sessions: [fallback],
        };
      }
      return {
        activeSessionId: remaining[0].id,
        sessions: remaining,
      };
    });
    setInput("");
    setError(null);
  };

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
    if (!activeSessionId) return;
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
    const targetSessionId = activeSessionId;
    const history = messages
      .filter((m) => (m.role === "user" || m.role === "assistant") && m.content.trim())
      .slice(-MAX_HISTORY_TURNS)
      .map((m) => ({ role: m.role as "user" | "assistant", content: m.content.trim() }));
    setInput("");
    updateMessagesForSession(targetSessionId, (prev) => [...prev, { role: "user", content: prompt }, { role: "assistant", content: "" }]);
    setLoading(true);
    const replaceLatestAssistant = (
      content: string,
      payload?: { citations?: ChatCitation[]; retrievalMeta?: ChatRetrievalMeta | null },
    ) => {
      updateMessagesForSession(targetSessionId, (prev) => {
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
      updateMessagesForSession(targetSessionId, (prev) => {
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
      updateMessagesForSession(targetSessionId, (prev) => {
        if (prev.length === 0) return prev;
        const last = prev[prev.length - 1];
        if (last.role === "assistant" && !last.content.trim()) {
          return prev.slice(0, -1);
        }
        return prev;
      });
    };
    const buildToolNotice = (toolCall: ChatToolCallEvent): string => {
      const scopeText = toolCall.scope === "paper" ? `paper #${toolCall.paper_id ?? "?"}` : "library";
      const tuning =
        typeof toolCall.candidate_k === "number" && typeof toolCall.final_k === "number"
          ? ` (candidate_k=${toolCall.candidate_k}, final_k=${toolCall.final_k})`
          : "";
      return `RAG tool call: searching ${scopeText}${tuning}.`;
    };
    const appendSystemNotice = (text: string) => {
      if (!text.trim()) return;
      updateMessagesForSession(targetSessionId, (prev) => {
        if (prev.some((message, index) => message.role === "system" && message.content === text && index >= prev.length - 3)) {
          return prev;
        }
        return [...prev, { role: "system", content: text }];
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
        history: history.length > 0 ? history : undefined,
        send_full_text: showDebug && debugSendFullText ? true : undefined,
      };
      const resp = await chatWithPaperStream(settings, payload, {
        onToolCall: (toolCall) => {
          appendSystemNotice(buildToolNotice(toolCall));
        },
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
            history: history.length > 0 ? history : undefined,
            send_full_text: showDebug && debugSendFullText ? true : undefined,
          });
          replaceLatestAssistant(fallback.answer || "", {
            citations: fallback.citations || [],
            retrievalMeta: fallback.retrieval_meta || null,
          });
          if (fallback.retrieval_meta?.tool_call_invoked) {
            appendSystemNotice(
              buildToolNotice({
                name: fallback.retrieval_meta.tool_call_name || "rag_search",
                scope: fallback.retrieval_meta.tool_call_scope || fallback.retrieval_meta.scope,
                paper_id: fallback.retrieval_meta.tool_call_paper_id ?? fallback.retrieval_meta.paper_filter,
                candidate_k: fallback.retrieval_meta.candidate_k,
                final_k: fallback.retrieval_meta.final_k_requested,
                reason: fallback.retrieval_meta.tool_call_reason || undefined,
              }),
            );
          }
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
        <div className="chat-header-main">
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <span className="chat-title">Conversation</span>
            {loading && <span className="pill info">Processing...</span>}
            <span className="pill info">Default: Library RAG</span>
            <span className="pill">{messages.length} messages</span>
            {paper?.id ? (
              <span className="pill">Selected paper #{paper.id}</span>
            ) : (
              <span className="pill">No paper selected</span>
            )}
          </div>
          <div className="chat-session-controls">
            <label className="chat-session-picker">
              <span>Session</span>
              <select
                value={activeSessionId}
                onChange={(event) => {
                  const nextSessionId = event.target.value;
                  updateSessionStore((prev) => ({ ...prev, activeSessionId: nextSessionId }));
                  setError(null);
                }}
                disabled={loading}
              >
                {sessionStore.sessions.map((session) => (
                  <option key={session.id} value={session.id}>
                    {session.title}
                  </option>
                ))}
              </select>
            </label>
            <button className="ghost-btn" onClick={createNewSession} disabled={loading}>
              New Session
            </button>
            <button
              className="ghost-btn"
              onClick={deleteCurrentSession}
              disabled={loading || sessionStore.sessions.length <= 1}
            >
              Delete Session
            </button>
          </div>
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
                    const normalizedPaperId = Number(citation.paper_id);
                    if (!Number.isFinite(normalizedPaperId) || normalizedPaperId <= 0 || paperMap.has(normalizedPaperId)) {
                      return;
                    }
                    paperMap.set(normalizedPaperId, {
                      paperId: normalizedPaperId,
                      title: citation.paper_title?.trim() || `Paper #${normalizedPaperId}`,
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
                            {m.retrievalMeta.tool_call_invoked ? " · tool: rag_search" : ""}
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
