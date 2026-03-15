export type TagType = "domain" | "task" | "keyword" | string;
export type ThemeMode = "dark" | "light";

export interface PaperListItem {
  id: number;
  key: string;
  title: string | null;
  item_type: string | null;
  year: number | null;
  doi: string | null;
  url: string | null;
}

export interface PaperListResponse {
  total: number;
  items: PaperListItem[];
}

export interface SummaryPayload {
  long_summary: string | null;
  one_liner: string | null;
  snarky_comment: string | null;
  model: string | null;
}

export interface TagPayload {
  type: TagType;
  value: string;
}

export interface AttachmentPayload {
  path: string;
  type: string | null;
}

export interface PaperDetail extends PaperListItem {
  authors: string | null;
  abstract: string | null;
  manual_tags: string | null;
  automatic_tags: string | null;
  summary: SummaryPayload | null;
  tags: TagPayload[];
  attachments: AttachmentPayload[];
  chunks_count: number;
}

export interface Settings {
  apiBase: string;
  llmBaseUrl: string;
  llmModel: string;
  llmApiKey: string;
  embedBaseUrl: string;
  embedModel: string;
  embedApiKey: string;
}

export interface ChatCitation {
  index: number;
  paper_id: number | null;
  chunk_id: number | null;
  seq: number | null;
  snippet: string;
  score: {
    vector?: number | null;
    rerank?: number | null;
  };
}

export interface ChatRetrievalMeta {
  scope: "library" | "paper";
  paper_filter: number | null;
  candidate_k: number;
  final_k_requested: number;
  final_k_used: number;
  rerank_enabled: boolean;
  legacy_direct_mode: boolean;
  legacy_fields_used?: string[];
  legacy_fields_deprecation?: string | null;
  context_char_budget: number;
  timings_ms: {
    retrieval: number;
    generation: number;
    total: number;
  };
}

export interface ChatResponse {
  answer: string;
  contexts: any[];
  citations: ChatCitation[];
  retrieval_meta: ChatRetrievalMeta;
}

export interface PipelineJob {
  job_id: string;
  job_type: string;
  status: string;
  running: boolean;
  returncode: number | null;
  params: Record<string, any>;
  stats: Record<string, any>;
  result?: Record<string, any> | null;
  error_type?: string | null;
  error_message?: string | null;
  last_message?: string | null;
  started_at?: string | null;
  updated_at?: string | null;
  finished_at?: string | null;
  resumed_from_id?: string | null;
  log?: string;
}
