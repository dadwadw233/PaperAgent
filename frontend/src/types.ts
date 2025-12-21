export type TagType = "domain" | "task" | "keyword" | string;

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
