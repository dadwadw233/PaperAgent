import { PaperDetail, PaperListResponse, Settings } from "./types";

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
  payload: { query: string; paper_id?: number; top_k?: number; use_embeddings?: boolean },
): Promise<{ answer: string; contexts: any[] }> {
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
): Promise<{ pdf_count: number; papers_with_pdf: number; papers_with_chunks: number; missing_papers: number; missing_pdfs: number; sample_missing: any[]; summary_rows: number; papers_with_summary: number; missing_summary: number }> {
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
