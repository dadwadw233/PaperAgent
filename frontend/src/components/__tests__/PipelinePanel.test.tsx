import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PipelinePanel } from "../PipelinePanel";
import type { Settings } from "../../types";
import {
  dedupeAttachments,
  fetchPipelineJobs,
  fetchPipelineStats,
  getEmbedStatus,
  getProcessPdfsStatus,
  getSummarizeStatus,
  resumePipelineJob,
  runProcessPdfs,
  startEmbedJob,
  stopEmbedJob,
  stopProcessPdfs,
  stopSummarize,
  triggerSummarize,
} from "../../api";

vi.mock("../../api", () => ({
  dedupeAttachments: vi.fn(),
  fetchPipelineStats: vi.fn(),
  fetchPipelineJobs: vi.fn(),
  getProcessPdfsStatus: vi.fn(),
  runProcessPdfs: vi.fn(),
  startEmbedJob: vi.fn(),
  getEmbedStatus: vi.fn(),
  stopEmbedJob: vi.fn(),
  triggerSummarize: vi.fn(),
  getSummarizeStatus: vi.fn(),
  stopSummarize: vi.fn(),
  stopProcessPdfs: vi.fn(),
  resumePipelineJob: vi.fn(),
}));

const mockedFetchPipelineStats = vi.mocked(fetchPipelineStats);
const mockedFetchPipelineJobs = vi.mocked(fetchPipelineJobs);
const mockedResumePipelineJob = vi.mocked(resumePipelineJob);
const mockedGetProcessPdfsStatus = vi.mocked(getProcessPdfsStatus);

const settings: Settings = {
  apiBase: "http://127.0.0.1:8000",
  llmBaseUrl: "",
  llmModel: "",
  llmApiKey: "",
  embedBaseUrl: "",
  embedModel: "",
  embedApiKey: "",
};

describe("PipelinePanel", () => {
  beforeEach(() => {
    vi.mocked(dedupeAttachments).mockResolvedValue({ status: "ok", result: {} });
    vi.mocked(runProcessPdfs).mockResolvedValue({ job_id: "pdf-job" });
    vi.mocked(startEmbedJob).mockResolvedValue({ job_id: "embed-job" });
    vi.mocked(getEmbedStatus).mockResolvedValue({ running: false, returncode: 0, log: "", stats: {} });
    vi.mocked(stopEmbedJob).mockResolvedValue({ status: "stopped" });
    vi.mocked(triggerSummarize).mockResolvedValue({ job_id: "sum-job" });
    vi.mocked(getSummarizeStatus).mockResolvedValue({ running: false, returncode: 0, log: "", stats: {} });
    vi.mocked(stopSummarize).mockResolvedValue({ status: "stopped" });
    vi.mocked(stopProcessPdfs).mockResolvedValue({ status: "stopped" });

    mockedFetchPipelineStats.mockResolvedValue({
      pdf_count: 10,
      papers_with_pdf: 9,
      papers_with_chunks: 8,
      missing_papers: 1,
      missing_pdfs: 1,
      sample_missing: [],
      summary_rows: 8,
      papers_with_summary: 8,
      missing_summary: 1,
      chunks_total: 88,
      embed_estimate: {
        persist_dir: "./chroma_store",
        collection: "paper_chunks",
        embedded_count: 80,
      },
    });
    mockedFetchPipelineJobs.mockResolvedValue([
      {
        job_id: "old-process-job",
        job_type: "process_pdfs",
        status: "interrupted",
        running: false,
        returncode: -1,
        params: {},
        stats: {},
        updated_at: "2026-03-15T10:00:00",
      },
    ]);
    mockedResumePipelineJob.mockResolvedValue({ job_id: "new-process-job" });
    mockedGetProcessPdfsStatus.mockResolvedValue({
      running: false,
      returncode: 0,
      log: "",
      stats: { processed_pdfs: 2, total_pdfs: 2, missing_files: 0 },
    });
  });

  it("loads and displays job history", async () => {
    render(<PipelinePanel settings={settings} />);

    expect(await screen.findByText("Job History")).toBeInTheDocument();
    expect(await screen.findByText("old-process-job", { exact: false })).toBeInTheDocument();
    expect(mockedFetchPipelineJobs).toHaveBeenCalledWith(settings, { limit: 30 });
  });

  it("resumes interrupted process job from history", async () => {
    const user = userEvent.setup();
    render(<PipelinePanel settings={settings} />);

    const resumeButton = await screen.findByRole("button", { name: "Resume" });
    await user.click(resumeButton);

    await waitFor(() => {
      expect(mockedResumePipelineJob).toHaveBeenCalledWith(settings, "old-process-job");
    });
    await waitFor(() => {
      expect(mockedGetProcessPdfsStatus).toHaveBeenCalledWith(settings, "new-process-job");
    });
  });
});
