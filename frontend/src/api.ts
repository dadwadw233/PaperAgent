import { ChatResponse, ChatToolCallEvent, PaperDetail, PaperListResponse, PipelineJob, Settings } from "./types";

function buildUrl(base: string, path: string, params?: Record<string, string | number | undefined>) {
  const url = new URL(path, base.endsWith("/") ? base : `${base}/`);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    });
  }
  return url.toString();
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Request failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function fetchPapers(
  settings: Settings,
  params: { q?: string; item_type?: string; search_fields?: string; limit?: number; offset?: number },
): Promise<PaperListResponse> {
  const url = buildUrl(settings.apiBase, "/papers", params);
  return fetchJson<PaperListResponse>(url);
}

export async function fetchPaperDetail(settings: Settings, id: number): Promise<PaperDetail> {
  const url = buildUrl(settings.apiBase, `/papers/${id}`);
  return fetchJson<PaperDetail>(url);
}

export async function fetchConfig(settings: Settings): Promise<Record<string, string>> {
  const url = buildUrl(settings.apiBase, "/config");
  const data = await fetchJson<{ entries: Record<string, string> }>(url);
  return data.entries;
}

export async function updateConfig(
  settings: Settings,
  entries: Record<string, string>,
): Promise<Record<string, string>> {
  const url = buildUrl(settings.apiBase, "/config");
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(entries),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Update config failed (${res.status}): ${text}`);
  }
  const data = await res.json();
  return data.entries;
}

export async function chatWithPaper(
  settings: Settings,
  payload: {
    query: string;
    scope?: "library" | "paper";
    paper_id?: number;
    candidate_k?: number;
    final_k?: number;
    rerank?: boolean;
    require_citations?: boolean;
    history?: Array<{ role: "user" | "assistant"; content: string }>;
    // Legacy compatibility
    top_k?: number;
    use_embeddings?: boolean;
    send_full_text?: boolean;
    max_chunks?: number;
  },
): Promise<ChatResponse> {
  const url = buildUrl(settings.apiBase, "/chat");
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Chat failed (${res.status}): ${text}`);
  }
  return res.json();
}

type ChatStreamHandlers = {
  onDelta?: (delta: string) => void;
  onFinal?: (finalPayload: ChatResponse) => void;
  onToolCall?: (toolCall: ChatToolCallEvent) => void;
};

export async function chatWithPaperStream(
  settings: Settings,
  payload: {
    query: string;
    scope?: "library" | "paper";
    paper_id?: number;
    candidate_k?: number;
    final_k?: number;
    rerank?: boolean;
    require_citations?: boolean;
    history?: Array<{ role: "user" | "assistant"; content: string }>;
    top_k?: number;
    use_embeddings?: boolean;
    send_full_text?: boolean;
    max_chunks?: number;
  },
  handlers: ChatStreamHandlers = {},
): Promise<ChatResponse> {
  const url = buildUrl(settings.apiBase, "/chat");
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ ...payload, stream: true }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Chat stream failed (${res.status}): ${text}`);
  }
  if (!res.body) {
    throw new Error("Chat stream failed: empty response body");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalPayload: ChatResponse | null = null;

  const flushEvent = (rawEvent: string) => {
    if (!rawEvent.trim()) return;
    let eventName = "message";
    const dataLines: string[] = [];
    rawEvent.split(/\r?\n/).forEach((line) => {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    });
    const dataText = dataLines.join("\n");
    if (!dataText) return;
    let payloadObj: any = {};
    try {
      payloadObj = JSON.parse(dataText);
    } catch {
      return;
    }
    if (eventName === "delta") {
      const delta = payloadObj?.delta;
      if (typeof delta === "string" && handlers.onDelta) {
        handlers.onDelta(delta);
      }
      return;
    }
    if (eventName === "final") {
      finalPayload = payloadObj as ChatResponse;
      if (handlers.onFinal) {
        handlers.onFinal(finalPayload);
      }
      return;
    }
    if (eventName === "tool_call") {
      if (handlers.onToolCall) {
        handlers.onToolCall(payloadObj as ChatToolCallEvent);
      }
      return;
    }
    if (eventName === "error") {
      throw new Error(payloadObj?.error || "Chat stream returned error event");
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      flushEvent(rawEvent);
      boundary = buffer.indexOf("\n\n");
    }
  }

  if (buffer.trim()) {
    flushEvent(buffer);
  }
  if (!finalPayload) {
    throw new Error("Chat stream ended without final payload");
  }
  return finalPayload;
}

export async function uploadCsv(
  settings: Settings,
  file: File,
  limit?: number,
): Promise<{ inserted: number; skipped: number; total_rows: number; non_papers: any[] }> {
  const form = new FormData();
  form.append("file", file);
  if (limit !== undefined) {
    form.append("limit", String(limit));
  }
  const url = buildUrl(settings.apiBase, "/import/csv");
  const res = await fetch(url, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function runProcessPdfs(
  settings: Settings,
  params: { chunk_size?: number; overlap?: number; limit?: number; skip_existing?: boolean },
): Promise<{ job_id: string }> {
  const url = buildUrl(settings.apiBase, "/pipeline/process_pdfs/start");
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Process PDFs failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function getProcessPdfsStatus(
  settings: Settings,
  job_id: string,
): Promise<{ running: boolean; returncode: number | null; log: string; stats?: any }> {
  const url = buildUrl(settings.apiBase, "/pipeline/process_pdfs/status", { job_id });
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Get status failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function stopProcessPdfs(settings: Settings, job_id: string): Promise<{ status: string }> {
  const url = buildUrl(settings.apiBase, "/pipeline/process_pdfs/stop");
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Stop process_pdfs failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function dedupeAttachments(settings: Settings): Promise<{ status: string; result: any }> {
  const url = buildUrl(settings.apiBase, "/pipeline/dedupe_attachments");
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Dedupe failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function startEmbedJob(
  settings: Settings,
  params: {
    limit_chunks?: number;
    collection?: string;
    persist_dir?: string;
    batch_size?: number;
    embed_base_url?: string;
    embed_model?: string;
    embed_api_key?: string;
    skip_existing?: boolean;
  },
): Promise<{ job_id: string }> {
  const url = buildUrl(settings.apiBase, "/pipeline/embed_chunks/start");
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Embed start failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function getEmbedStatus(
  settings: Settings,
  job_id: string,
): Promise<{ running: boolean; returncode: number | null; log: string; stats?: any; last_message?: string }> {
  const url = buildUrl(settings.apiBase, "/pipeline/embed_chunks/status", { job_id });
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Embed status failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function stopEmbedJob(settings: Settings, job_id: string): Promise<{ status: string }> {
  const url = buildUrl(settings.apiBase, "/pipeline/embed_chunks/stop");
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Stop embed failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function triggerSummarize(
  settings: Settings,
  params: { limit?: number; chunk_chars?: number; skip_existing?: boolean; dry_run?: boolean },
): Promise<{ job_id: string }> {
  const url = buildUrl(settings.apiBase, "/pipeline/summarize/start");
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Summarize failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function getSummarizeStatus(
  settings: Settings,
  job_id: string,
): Promise<{ running: boolean; returncode: number | null; log: string; stats?: any; last_message?: string }> {
  const url = buildUrl(settings.apiBase, "/pipeline/summarize/status", { job_id });
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Summarize status failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function stopSummarize(settings: Settings, job_id: string): Promise<{ status: string }> {
  const url = buildUrl(settings.apiBase, "/pipeline/summarize/stop");
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Stop summarize failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function fetchPipelineStats(
  settings: Settings,
): Promise<{
  pdf_count: number;
  papers_with_pdf: number;
  papers_with_chunks: number;
  missing_papers: number;
  missing_pdfs: number;
  sample_missing: any[];
  summary_rows: number;
  papers_with_summary: number;
  missing_summary: number;
  chunks_total?: number;
  embed_estimate?: { persist_dir: string; collection: string; embedded_count: number } | null;
}> {
  const url = buildUrl(settings.apiBase, "/pipeline/stats");
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Stats failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function clearSummary(settings: Settings, paperId: number): Promise<{ deleted_summary: number; deleted_tags: number }> {
  const url = buildUrl(settings.apiBase, "/pipeline/clear_summary");
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ paper_id: paperId }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Clear summary failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function fetchPipelineJobs(
  settings: Settings,
  params?: { limit?: number; job_type?: string },
): Promise<PipelineJob[]> {
  const url = buildUrl(settings.apiBase, "/pipeline/jobs", params);
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Pipeline jobs failed (${res.status}): ${text}`);
  }
  const data = await res.json();
  return data.items || [];
}

export async function fetchPipelineJob(settings: Settings, jobId: string): Promise<PipelineJob> {
  const url = buildUrl(settings.apiBase, `/pipeline/jobs/${jobId}`);
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Pipeline job detail failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function resumePipelineJob(settings: Settings, jobId: string): Promise<{ job_id: string }> {
  const url = buildUrl(settings.apiBase, `/pipeline/jobs/${jobId}/resume`);
  const res = await fetch(url, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Pipeline resume failed (${res.status}): ${text}`);
  }
  return res.json();
}

export async function deletePipelineJob(settings: Settings, jobId: string): Promise<{ status: string; job_id: string }> {
  const url = buildUrl(settings.apiBase, `/pipeline/jobs/${jobId}`);
  const res = await fetch(url, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Pipeline delete failed (${res.status}): ${text}`);
  }
  return res.json();
}
