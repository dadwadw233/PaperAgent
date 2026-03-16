import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatPanel } from "../ChatPanel";
import type { PaperDetail, Settings } from "../../types";
import { chatWithPaper, chatWithPaperStream } from "../../api";

vi.mock("../../api", () => ({
  chatWithPaper: vi.fn(),
  chatWithPaperStream: vi.fn(),
}));

const mockedChatWithPaper = vi.mocked(chatWithPaper);
const mockedChatWithPaperStream = vi.mocked(chatWithPaperStream);

const settings: Settings = {
  apiBase: "http://127.0.0.1:8000",
  llmBaseUrl: "http://127.0.0.1:11434/v1",
  llmModel: "test-llm",
  llmApiKey: "secret",
  embedBaseUrl: "http://127.0.0.1:11434/v1",
  embedModel: "test-embed",
  embedApiKey: "secret",
};

const paper: PaperDetail = {
  id: 7,
  key: "paper-7",
  title: "Paper Seven",
  item_type: "journalArticle",
  year: 2025,
  doi: null,
  url: null,
  authors: null,
  abstract: null,
  manual_tags: null,
  automatic_tags: null,
  summary: null,
  tags: [],
  attachments: [],
  chunks_count: 4,
};

const chatResponse = {
  answer: "Grounded answer [1].",
  contexts: [],
  citations: [
    {
      index: 1,
      paper_id: 7,
      paper_title: "Paper Seven",
      chunk_id: 77,
      seq: 1,
      snippet: "evidence snippet",
      score: {
        vector: 0.9,
        rerank: 0.7,
      },
    },
  ],
  retrieval_meta: {
    scope: "library" as const,
    paper_filter: null,
    candidate_k: 20,
    final_k_requested: 6,
    final_k_used: 1,
    rerank_enabled: true,
    legacy_direct_mode: false,
    context_char_budget: 7000,
    timings_ms: {
      retrieval: 11,
      generation: 33,
      total: 44,
    },
  },
};

describe("ChatPanel", () => {
  beforeEach(() => {
    mockedChatWithPaper.mockReset();
    mockedChatWithPaperStream.mockReset();
    mockedChatWithPaper.mockResolvedValue(chatResponse);
    mockedChatWithPaperStream.mockImplementation(async (_settings, _payload, handlers = {}) => {
      handlers.onDelta?.("Grounded ");
      handlers.onFinal?.(chatResponse);
      return chatResponse;
    });
  });

  it("sends library-scope payload without selected paper", async () => {
    const user = userEvent.setup();
    render(<ChatPanel paper={null} settings={settings} />);

    await user.type(screen.getByPlaceholderText("Ask a question about your papers..."), "What is new?");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(mockedChatWithPaperStream).toHaveBeenCalledTimes(1));
    expect(mockedChatWithPaperStream).toHaveBeenCalledWith(
      settings,
      expect.objectContaining({
        query: "What is new?",
        scope: "library",
        paper_id: undefined,
        candidate_k: 20,
        final_k: 6,
        rerank: true,
        require_citations: true,
      }),
      expect.any(Object),
    );
    expect(await screen.findByText("Grounded answer [1].")).toBeInTheDocument();
  });

  it("sends paper scope with selected paper id", async () => {
    const user = userEvent.setup();
    render(<ChatPanel paper={paper} settings={settings} />);

    await user.click(screen.getByRole("radio", { name: "Current paper only" }));
    await user.type(screen.getByPlaceholderText("Ask a question about your papers..."), "Summarize this paper");
    await user.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(mockedChatWithPaperStream).toHaveBeenCalledTimes(1));
    expect(mockedChatWithPaperStream).toHaveBeenCalledWith(
      settings,
      expect.objectContaining({
        scope: "paper",
        paper_id: 7,
      }),
      expect.any(Object),
    );
  });

  it("renders citation panel and supports jump callback", async () => {
    const user = userEvent.setup();
    const onJump = vi.fn();
    render(<ChatPanel paper={paper} settings={settings} onJumpToPaper={onJump} />);

    await user.type(screen.getByPlaceholderText("Ask a question about your papers..."), "Need citation details");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Sources (1 papers)")).toBeInTheDocument();
    await user.click(screen.getByText("Sources (1 papers)"));
    await user.click(screen.getByRole("button", { name: "Open" }));
    expect(onJump).toHaveBeenCalledWith(7);
  });
});
