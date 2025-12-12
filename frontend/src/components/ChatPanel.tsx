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
      });
      const ctxSummary = resp.contexts
        ?.map((c: any, idx: number) => `[${idx + 1}] paper ${c.paper_id} seq ${c.seq}`)
        ?.join(" ");
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
    <div className="panel chat">
      <div className="panel-header">
        <div className="pill">Chat</div>
        {!paper && <div className="pill warn">Select a paper first</div>}
        {loading && <div className="pill">Thinking…</div>}
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
        <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <input
            type="checkbox"
            checked={useEmbeddings}
            onChange={(e) => setUseEmbeddings(e.target.checked)}
            disabled={disabled || loading}
          />
          <span className="muted">使用向量检索</span>
        </label>
        <span className="muted" style={{ fontSize: 12 }}>
          勾选后按相似度召回 chunk（需已运行嵌入）
        </span>
      </div>
      <div className="chat-messages">
        {messages.map((m, idx) => (
          <div className="chat-row" key={idx}>
            <div className="role">{m.role}</div>
            <div className="bubble">{m.content}</div>
          </div>
        ))}
        {paper && (
          <div className="chat-row">
            <div className="role">context</div>
            <div className="bubble">
              Loaded paper: <strong>{paper.title}</strong>
            </div>
          </div>
        )}
        {error && (
          <div className="chat-row">
            <div className="role">error</div>
            <div className="bubble">{error}</div>
          </div>
        )}
      </div>
      <div className="chat-input">
        <textarea
          placeholder={disabled ? "Pick a paper to start chatting" : "Ask or critique this paper..."}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={disabled || loading}
        />
        <button className="primary-btn" onClick={send} disabled={disabled || loading}>
          Send
        </button>
      </div>
    </div>
  );
};
