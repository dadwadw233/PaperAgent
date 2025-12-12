import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  dedupeAttachments,
  fetchPipelineStats,
  getProcessPdfsStatus,
  runProcessPdfs,
  startEmbedJob,
  getEmbedStatus,
  stopEmbedJob,
  triggerSummarize,
  getSummarizeStatus,
  stopSummarize,
  stopProcessPdfs,
} from "../api";
import { Settings } from "../types";

interface Props {
  settings: Settings;
  onSummaryFinished?: () => void;
}

type PipelineStats = {
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
};

export const PipelinePanel: React.FC<Props> = ({ settings, onSummaryFinished }) => {
  // PDF Processing State
  const [chunkSize, setChunkSize] = useState("1200");
  const [overlap, setOverlap] = useState("200");
  const [pdfLimit, setPdfLimit] = useState("");
  const [skipExistingChunks, setSkipExistingChunks] = useState(true);
  const [pdfJobId, setPdfJobId] = useState<string | null>(null);
  const [pdfRunning, setPdfRunning] = useState(false);
  const [pdfProgress, setPdfProgress] = useState<{ processed_pdfs?: number; total_pdfs?: number; missing_files?: number }>({});
  const [pdfError, setPdfError] = useState<string | null>(null);

  // Embedding State
  const [embedModel, setEmbedModel] = useState(settings.embedModel || settings.llmModel || "");
  const [embedLimit, setEmbedLimit] = useState<string>("");
  const [skipExistingEmbeds, setSkipExistingEmbeds] = useState(true);
  const [embedJobId, setEmbedJobId] = useState<string | null>(null);
  const [embedRunning, setEmbedRunning] = useState(false);
  const [embedProgress, setEmbedProgress] = useState<{ embedded?: number; total?: number; skipped?: number }>({});
  const [embedError, setEmbedError] = useState<string | null>(null);

  // Summary State
  const [summLimit, setSummLimit] = useState<string>("");
  const [summDryRun, setSummDryRun] = useState(false);
  const [skipExistingSummaries, setSkipExistingSummaries] = useState(true);
  const [summJobId, setSummJobId] = useState<string | null>(null);
  const [summRunning, setSummRunning] = useState(false);
  const [summProgress, setSummProgress] = useState<{
    processed?: number;
    total?: number;
    skipped?: number;
    errors?: number;
  }>({});
  const [summError, setSummError] = useState<string | null>(null);
  const [summResult, setSummResult] = useState<{
    processed: number;
    skipped: number;
    errors: number;
    total: number;
  } | null>(null);

  // Stats State
  const [stats, setStats] = useState<PipelineStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  useEffect(() => {
    setEmbedModel(settings.embedModel || settings.llmModel || "");
  }, [settings.embedModel, settings.llmModel]);

  const pdfPercent = useMemo(() => {
    const done = pdfProgress.processed_pdfs || 0;
    const total = pdfProgress.total_pdfs || 0;
    if (!total) return 0;
    return Math.min(100, Math.round((done / total) * 100));
  }, [pdfProgress]);

  const embedPercent = useMemo(() => {
    const done = (embedProgress.embedded || 0) + (embedProgress.skipped || 0);
    const total = embedProgress.total || 0;
    if (!total) return 0;
    return Math.min(100, Math.round((done / total) * 100));
  }, [embedProgress]);

  const summPercent = useMemo(() => {
    const done = summProgress.processed || 0;
    const total = summProgress.total || 0;
    if (!total) return 0;
    return Math.min(100, Math.round((done / total) * 100));
  }, [summProgress]);

  const loadStats = async () => {
    setStatsLoading(true);
    try {
      const data = await fetchPipelineStats(settings);
      setStats(data);
    } catch (err) {
      console.error("Failed to load stats:", err);
    } finally {
      setStatsLoading(false);
    }
  };

  useEffect(() => {
    loadStats();
  }, [settings.apiBase]);

  const runPdfProcessing = async () => {
    setPdfError(null);
    setPdfJobId(null);
    setPdfRunning(false);
    setPdfProgress({});
    try {
      const resp = await runProcessPdfs(settings, {
        chunk_size: Number(chunkSize) || 1200,
        overlap: Number(overlap) || 200,
        limit: pdfLimit ? Number(pdfLimit) : undefined,
        skip_existing: skipExistingChunks,
      });
      setPdfJobId(resp.job_id);
      setPdfRunning(true);
      pollPdfStatus(resp.job_id);
    } catch (err) {
      setPdfError(err instanceof Error ? err.message : "Failed to start PDF processing");
    }
  };

  const pollPdfStatus = async (jid: string) => {
    const tick = async () => {
      try {
        const status = await getProcessPdfsStatus(settings, jid);
        setPdfRunning(status.running);
        setPdfJobId(jid);
        if (status.stats) {
          setPdfProgress({
            processed_pdfs: status.stats.processed_pdfs,
            total_pdfs: status.stats.total_pdfs,
            missing_files: status.stats.missing_files,
          });
        }
        if (status.running) {
          setTimeout(tick, 2000);
        } else {
          if (status.returncode !== null && status.returncode !== 0) {
            setPdfError(`Processing failed (exit code: ${status.returncode})`);
          }
          loadStats();
        }
      } catch (err) {
        setPdfError(err instanceof Error ? err.message : "Failed to fetch status");
        setPdfRunning(false);
      }
    };
    tick();
  };

  const runEmbedding = async () => {
    setEmbedError(null);
    setEmbedProgress({});
    try {
      const resp = await startEmbedJob(settings, {
        limit_chunks: embedLimit ? Number(embedLimit) : undefined,
        embed_model: embedModel || undefined,
        embed_base_url: settings.embedBaseUrl || settings.llmBaseUrl || undefined,
        embed_api_key: settings.embedApiKey || settings.llmApiKey || undefined,
        batch_size: 16,
        skip_existing: skipExistingEmbeds,
      });
      setEmbedJobId(resp.job_id);
      setEmbedRunning(true);
      pollEmbedStatus(resp.job_id);
    } catch (err) {
      setEmbedError(err instanceof Error ? err.message : "Failed to start embedding");
    }
  };

  const pollEmbedStatus = async (jid: string) => {
    const tick = async () => {
      try {
        const status = await getEmbedStatus(settings, jid);
        const statsPayload = status.stats || {};
        setEmbedProgress({
          embedded: statsPayload.embedded ?? 0,
          total: statsPayload.total_chunks ?? 0,
          skipped: statsPayload.embedded_skipped ?? 0,
        });
        setEmbedRunning(status.running);
        if (!status.running) {
          setEmbedJobId(null);
          if (status.returncode && status.returncode !== 0) {
            setEmbedError(`Embedding failed (exit code: ${status.returncode})`);
          }
          loadStats();
        }
        if (status.running) {
          setTimeout(tick, 2000);
        }
      } catch (err) {
        setEmbedError(err instanceof Error ? err.message : "Failed to fetch embed status");
        setEmbedRunning(false);
      }
    };
    tick();
  };

  const runSummarization = async () => {
    setSummError(null);
    setSummResult(null);
    setSummProgress({});
    try {
      const resp = await triggerSummarize(settings, {
        limit: summLimit ? Number(summLimit) : undefined,
        chunk_chars: 4000,
        skip_existing: skipExistingSummaries,
        dry_run: summDryRun,
      });
      setSummJobId(resp.job_id);
      setSummRunning(true);
      pollSummStatus(resp.job_id);
    } catch (err) {
      setSummError(err instanceof Error ? err.message : "Failed to start summarization");
    }
  };

  const pollSummStatus = async (jid: string) => {
    const tick = async () => {
      try {
        const status = await getSummarizeStatus(settings, jid);
        const statsPayload = status.stats || {};
        const processedCount = statsPayload.processed_papers ?? statsPayload.processed ?? 0;
        const totalCount = statsPayload.total_papers || processedCount;
        const skippedCount = statsPayload.skipped ?? 0;
        setSummProgress({
          processed: processedCount,
          total: totalCount,
          skipped: skippedCount,
          errors: statsPayload.errors ?? 0,
        });
        setSummRunning(status.running);
        if (!status.running) {
          setSummJobId(null);
          if (status.returncode && status.returncode !== 0) {
            setSummError(`Summarization failed (exit code: ${status.returncode})`);
          } else {
            setSummResult({
              processed: processedCount,
              skipped: skippedCount,
              errors: statsPayload.errors ?? 0,
              total: totalCount,
            });
            onSummaryFinished?.();
          }
          loadStats();
        }
        if (status.running) {
          setTimeout(tick, 2000);
        }
      } catch (err) {
        setSummError(err instanceof Error ? err.message : "Failed to fetch summary status");
        setSummRunning(false);
      }
    };
    tick();
  };

  return (
    <>
      {/* PDF Processing */}
      <div className="action-card">
        <div className="action-card-header">
          <h3 className="action-card-title">PDF Processing</h3>
          {pdfRunning && (
            <span className="pill info">
              {pdfProgress.processed_pdfs || 0}/{pdfProgress.total_pdfs || "?"}
            </span>
          )}
        </div>
        <div className="action-card-body">
          <p className="action-description">
            Extract text from PDFs and split into chunks for embedding and retrieval.
          </p>
          
          {pdfRunning && pdfProgress.total_pdfs ? (
            <div>
              <div className="progress-track">
                <div className="progress-fill" style={{ width: `${pdfPercent}%` }} />
              </div>
              <div className="summary-progress-meta" style={{ marginTop: 8 }}>
                <span>Processed: {pdfProgress.processed_pdfs || 0}/{pdfProgress.total_pdfs}</span>
                {pdfProgress.missing_files ? <span>Missing: {pdfProgress.missing_files}</span> : null}
              </div>
            </div>
          ) : null}

          <div className="stack">
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div className="settings-row">
                <label>Chunk Size</label>
                <input value={chunkSize} onChange={(e) => setChunkSize(e.target.value)} />
              </div>
              <div className="settings-row">
                <label>Overlap</label>
                <input value={overlap} onChange={(e) => setOverlap(e.target.value)} />
              </div>
            </div>
            <div className="settings-row">
              <label>Limit (optional)</label>
              <input
                value={pdfLimit}
                onChange={(e) => setPdfLimit(e.target.value)}
                placeholder="Leave empty to process all"
              />
            </div>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={skipExistingChunks}
                onChange={(e) => setSkipExistingChunks(e.target.checked)}
              />
              <span>Skip existing chunks</span>
            </label>
            <div style={{ display: "flex", gap: 12 }}>
              <button className="primary-btn" onClick={runPdfProcessing} disabled={pdfRunning}>
                {pdfRunning ? "Processing..." : "Start Processing"}
              </button>
              {pdfRunning && pdfJobId && (
                <button
                  className="ghost-btn"
                  onClick={async () => {
                    try {
                      await stopProcessPdfs(settings, pdfJobId);
                      setPdfRunning(false);
                    } catch (err) {
                      setPdfError(err instanceof Error ? err.message : "Failed to stop");
                    }
                  }}
                >
                  Stop
                </button>
              )}
            </div>
            {pdfError && <div className="error-banner">{pdfError}</div>}
          </div>
        </div>
      </div>

      {/* Embedding */}
      <div className="action-card">
        <div className="action-card-header">
          <h3 className="action-card-title">Vector Embeddings</h3>
          {embedRunning && (
            <span className="pill info">
              {embedProgress.embedded || 0}/{embedProgress.total || "?"}
            </span>
          )}
        </div>
        <div className="action-card-body">
          <p className="action-description">
            Generate vector embeddings for text chunks to enable semantic search.
          </p>

          {embedRunning && embedProgress.total ? (
            <div>
              <div className="progress-track">
                <div className="progress-fill" style={{ width: `${embedPercent}%` }} />
              </div>
              <div className="summary-progress-meta" style={{ marginTop: 8 }}>
                <span>Embedded: {embedProgress.embedded || 0}/{embedProgress.total}</span>
                <span>Skipped: {embedProgress.skipped || 0}</span>
              </div>
            </div>
          ) : null}

          <div className="stack">
            <div className="settings-row">
              <label>Embedding Model</label>
              <input
                value={embedModel}
                onChange={(e) => setEmbedModel(e.target.value)}
                placeholder="e.g., text-embedding-3-large"
              />
            </div>
            <div className="settings-row">
              <label>Limit (optional)</label>
              <input
                value={embedLimit}
                onChange={(e) => setEmbedLimit(e.target.value)}
                placeholder="Leave empty to process all"
              />
            </div>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={skipExistingEmbeds}
                onChange={(e) => setSkipExistingEmbeds(e.target.checked)}
                disabled={embedRunning}
              />
              <span>Skip already embedded chunks</span>
            </label>
            <div style={{ display: "flex", gap: 12 }}>
              <button className="primary-btn" onClick={runEmbedding} disabled={embedRunning}>
                {embedRunning ? "Embedding..." : "Start Embedding"}
              </button>
              {embedRunning && embedJobId && (
                <button
                  className="ghost-btn"
                  onClick={async () => {
                    try {
                      await stopEmbedJob(settings, embedJobId);
                      setEmbedRunning(false);
                    } catch (err) {
                      setEmbedError(err instanceof Error ? err.message : "Failed to stop");
                    }
                  }}
                >
                  Stop
                </button>
              )}
            </div>
            {embedError && <div className="error-banner">{embedError}</div>}
          </div>
        </div>
      </div>

      {/* Summarization */}
      <div className="action-card">
        <div className="action-card-header">
          <h3 className="action-card-title">AI Summarization</h3>
          {summRunning && (
            <span className="pill info">
              {summProgress.processed || 0}/{summProgress.total || "?"}
            </span>
          )}
        </div>
        <div className="action-card-body">
          <p className="action-description">
            Generate AI-powered summaries, one-liners, and tags for papers.
          </p>

          {summRunning && summProgress.total ? (
            <div>
              <div className="progress-track">
                <div className="progress-fill" style={{ width: `${summPercent}%` }} />
              </div>
              <div className="summary-progress-meta" style={{ marginTop: 8 }}>
                <span>Processed: {summProgress.processed || 0}/{summProgress.total}</span>
                <span>Errors: {summProgress.errors || 0}</span>
                {summProgress.skipped ? <span>Skipped: {summProgress.skipped}</span> : null}
              </div>
            </div>
          ) : null}

          <div className="stack">
            <div className="settings-row">
              <label>Limit (optional)</label>
              <input
                value={summLimit}
                onChange={(e) => setSummLimit(e.target.value)}
                placeholder="Leave empty to process all"
              />
            </div>
            <div style={{ display: "flex", gap: 16 }}>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={skipExistingSummaries}
                  onChange={(e) => setSkipExistingSummaries(e.target.checked)}
                  disabled={summRunning}
                />
                <span>Skip existing summaries</span>
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={summDryRun}
                  onChange={(e) => setSummDryRun(e.target.checked)}
                />
                <span>Dry run</span>
              </label>
            </div>
            <div style={{ display: "flex", gap: 12 }}>
              <button className="primary-btn" onClick={runSummarization} disabled={summRunning}>
                {summRunning ? "Summarizing..." : "Start Summarization"}
              </button>
              {summRunning && summJobId && (
                <button
                  className="ghost-btn"
                  onClick={async () => {
                    try {
                      await stopSummarize(settings, summJobId);
                      setSummRunning(false);
                    } catch (err) {
                      setSummError(err instanceof Error ? err.message : "Failed to stop");
                    }
                  }}
                >
                  Stop
                </button>
              )}
            </div>
            {!summRunning && summResult && !summError && (
              <div className="success-banner">
                Summarization finished. Processed {summResult.processed}/{summResult.total}, skipped {summResult.skipped}, errors {summResult.errors}.
              </div>
            )}
            {summError && <div className="error-banner">{summError}</div>}
          </div>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="action-card">
          <div className="action-card-header">
            <h3 className="action-card-title">Pipeline Statistics</h3>
            <button className="ghost-btn" onClick={loadStats} disabled={statsLoading}>
              Refresh
            </button>
          </div>
          <div className="action-card-body">
            <div style={{ display: "grid", gap: 8, fontSize: 13 }}>
              <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: 8 }}>
                <span className="muted">Total PDFs:</span>
                <span>{stats.pdf_count}</span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: 8 }}>
                <span className="muted">Papers with PDFs:</span>
                <span>{stats.papers_with_pdf}</span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: 8 }}>
                <span className="muted">Papers with chunks:</span>
                <span>{stats.papers_with_chunks}</span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: 8 }}>
                <span className="muted">Papers with summaries:</span>
                <span>{stats.papers_with_summary}</span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: 8 }}>
                <span className="muted">Total chunks:</span>
                <span>{stats.chunks_total ?? "N/A"}</span>
              </div>
              {stats.embed_estimate && (
                <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: 8 }}>
                  <span className="muted">Embedded chunks:</span>
                  <span>{stats.embed_estimate.embedded_count}/{stats.chunks_total ?? "?"}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
};
