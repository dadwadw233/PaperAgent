import React, { useState } from "react";
import { chatWithPaper } from "../api";
import { PaperDetail, Settings } from "../types";

interface Props {
  paper: PaperDetail | null;
  settings: Settings;
}

interface Message {
  role: "user" | "assistant" | "system";
  content: string;
}

export const ChatPanel: React.FC<Props> = ({ paper, settings }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [useEmbeddings, setUseEmbeddings] = useState(false);
  const [sendFullText, setSendFullText] = useState(false);
  const [maxChunks, setMaxChunks] = useState(4);
  const disabled = !paper;

  const send = async () => {
    if (!input.trim()) return;
    if (!paper) return;
    setError(null);
    const prompt = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: prompt }]);
    setLoading(true);
    try {
      const resp = await chatWithPaper(settings, {
        query: prompt,
        paper_id: paper?.id,
        top_k: 4,
        use_embeddings: useEmbeddings,
        send_full_text: sendFullText,
        max_chunks: sendFullText ? undefined : maxChunks,
      });
      // Generate concise context summary
      let ctxSummary = "";
      if (resp.contexts && resp.contexts.length > 0) {
        const count = resp.contexts.length;
        if (count <= 5) {
          // Show detailed list for small number of chunks
          ctxSummary = resp.contexts
            .map((c: any, idx: number) => `[${idx + 1}] seq ${c.seq}`)
            .join(", ");
        } else {
          // Show concise summary for large number of chunks
          const firstSeq = resp.contexts[0]?.seq;
          const lastSeq = resp.contexts[count - 1]?.seq;
          ctxSummary = `${count} chunks (seq ${firstSeq}-${lastSeq})`;
        }
      }
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: resp.answer + (ctxSummary ? `\n\n(Context: ${ctxSummary})` : "") },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat failed");
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
          {paper && paper.chunks_count !== undefined && (
            <span className="pill" style={{ fontSize: "0.85em" }}>
              {paper.chunks_count} chunks available
            </span>
          )}
        </div>
        {!paper && <span className="pill warn">Select a paper first</span>}
      </div>
      <div className="chat-options">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={useEmbeddings}
            onChange={(e) => setUseEmbeddings(e.target.checked)}
            disabled={disabled || loading}
          />
          <span>Use vector search</span>
        </label>
        <span className="muted">Retrieve relevant chunks by similarity (requires embeddings)</span>

        <label className="checkbox-label" style={{ marginTop: "8px" }}>
          <input
            type="checkbox"
            checked={sendFullText}
            onChange={(e) => setSendFullText(e.target.checked)}
            disabled={disabled || loading}
          />
          <span>Send full text</span>
        </label>
        <span className="muted">Send all chunks from the paper (may be very long)</span>

        {!sendFullText && (
          <div style={{ marginTop: "12px" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ minWidth: "100px" }}>Chunks: {maxChunks}</span>
              <input
                type="range"
                min="1"
                max={paper?.chunks_count || 50}
                value={Math.min(maxChunks, paper?.chunks_count || 50)}
                onChange={(e) => setMaxChunks(Number(e.target.value))}
                disabled={disabled || loading}
                style={{ flex: 1 }}
              />
            </label>
            <span className="muted">
              Adjust how many chunks to send (1-{paper?.chunks_count || 50}
              {paper && ` total`})
            </span>
          </div>
        )}
      </div>
      <div className="chat-messages">
        {messages.length === 0 && !paper && (
          <div className="empty">Select a paper and start chatting</div>
        )}
        {messages.length === 0 && paper && (
          <div className="chat-row">
            <div className="role">system</div>
            <div className="bubble">
              Paper loaded: <strong>{paper.title}</strong>
              <br />
              <span className="muted">You can now ask questions about this paper.</span>
            </div>
          </div>
        )}
        {messages.map((m, idx) => (
          <div className="chat-row" key={idx}>
            <div className="role">{m.role}</div>
            <div className="bubble">{m.content}</div>
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
          placeholder={disabled ? "Select a paper to start chatting" : "Ask a question about this paper..."}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          disabled={disabled || loading}
        />
        <button className="primary-btn" onClick={send} disabled={disabled || loading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  );
};
