import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  dedupeAttachments,
  fetchPipelineStats,
  getProcessPdfsStatus,
  runProcessPdfs,
  startEmbedJob,
  getEmbedStatus,
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

export const PipelinePanel: React.FC<Props> = ({ settings, onSummaryFinished }) => {
  const [chunkSize, setChunkSize] = useState("1200");
  const [overlap, setOverlap] = useState("200");
  const [limit, setLimit] = useState("");
  const [skipExistingChunks, setSkipExistingChunks] = useState(true);
  const [output, setOutput] = useState("");
  const [stderr, setStderr] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<{ processed_pdfs?: number; total_pdfs?: number; missing_files?: number }>({});
  const [dedupeStatus, setDedupeStatus] = useState<string>("");
  const [embedStatus, setEmbedStatus] = useState<string>("");
  const [embedError, setEmbedError] = useState<string | null>(null);
  const [embedJobId, setEmbedJobId] = useState<string | null>(null);
  const [embedRunning, setEmbedRunning] = useState(false);
  const [embedLog, setEmbedLog] = useState("");
  const [embedProgress, setEmbedProgress] = useState<{ embedded?: number; total?: number }>({});
  const [embedModel, setEmbedModel] = useState(settings.embedModel || settings.llmModel || "");
  const [embedLimit, setEmbedLimit] = useState<string>("");
  const [summStatus, setSummStatus] = useState<string>("");
  const [summLimit, setSummLimit] = useState<string>("");
  const [summDryRun, setSummDryRun] = useState(false);
  const [summJobId, setSummJobId] = useState<string | null>(null);
  const [summRunning, setSummRunning] = useState(false);
  const [summLog, setSummLog] = useState("");
  const [summProgress, setSummProgress] = useState<{
    processed?: number;
    total?: number;
    errors?: number;
    current_paper_title?: string;
  }>({});
  const [summError, setSummError] = useState<string | null>(null);
  const [summTargetTotal, setSummTargetTotal] = useState<number | null>(null);
  const summTargetRef = useRef<number | null>(null);
  const [stats, setStats] = useState<null | {
    pdf_count: number;
    papers_with_pdf: number;
    papers_with_chunks: number;
    missing_papers: number;
    missing_pdfs: number;
    sample_missing: any[];
    summary_rows: number;
    papers_with_summary: number;
    missing_summary: number;
  }>(null);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [summaryFinishedNotified, setSummaryFinishedNotified] = useState(false);

  const progressPercent = useMemo(() => {
    const done = progress.processed_pdfs || 0;
    const total = progress.total_pdfs || 0;
    if (!total) return 0;
    return Math.min(100, Math.round((done / total) * 100));
  }, [progress]);

  const summPercent = useMemo(() => {
    const done = summProgress.processed || 0;
    const total = summProgress.total || 0;
    if (!total) return 0;
    return Math.min(100, Math.round((done / total) * 100));
  }, [summProgress]);

  const embedPercent = useMemo(() => {
    const done = embedProgress.embedded || 0;
    const total = embedProgress.total || 0;
    if (!total) return 0;
    return Math.min(100, Math.round((done / total) * 100));
  }, [embedProgress]);

  useEffect(() => {
    // Sync embed model from settings when it changes.
    setEmbedModel(settings.embedModel || settings.llmModel || "");
  }, [settings.embedModel, settings.llmModel]);

  const resolveSummaryTarget = useCallback(
    async (limitValue?: number | null) => {
      if (limitValue && limitValue > 0) {
        return limitValue;
      }
      try {
        const remoteStats = await fetchPipelineStats(settings);
        setStats(remoteStats);
        return remoteStats.missing_summary || null;
      } catch (err) {
        console.warn("Failed to resolve summary target", err);
        if (stats && typeof stats.missing_summary === "number") {
          return stats.missing_summary || null;
        }
        return null;
      }
    },
    [stats, settings],
  );

  const run = async () => {
    setLoading(true);
    setError(null);
    setOutput("");
    setStderr("");
    setJobId(null);
    setRunning(false);
    setProgress({});
    try {
      const resp = await runProcessPdfs(settings, {
        chunk_size: Number(chunkSize) || 1200,
        overlap: Number(overlap) || 200,
        limit: limit ? Number(limit) : undefined,
        skip_existing: skipExistingChunks,
      });
      setJobId(resp.job_id);
      setRunning(true);
      pollStatus(resp.job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "运行失败");
    } finally {
      setLoading(false);
    }
  };

  const pollStatus = async (jid: string) => {
    let attempts = 0;
    const tick = async () => {
      attempts += 1;
      try {
        const status = await getProcessPdfsStatus(settings, jid);
        setOutput(status.log || "");
        setStderr("");
        setRunning(status.running);
        setJobId(jid);
        if (status.stats) {
          setProgress({
            processed_pdfs: status.stats.processed_pdfs,
            total_pdfs: status.stats.total_pdfs,
            missing_files: status.stats.missing_files,
          });
        }
        if (status.running) {
          setTimeout(tick, 2000);
        } else {
          if (status.returncode !== null && status.returncode !== 0) {
            setError(`运行失败 (code=${status.returncode})`);
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "获取状态失败");
        setRunning(false);
      }
    };
    tick();
  };

  const pollEmbed = async (jid: string) => {
    try {
      const status = await getEmbedStatus(settings, jid);
      setEmbedLog(status.log || "");
      const statsPayload = status.stats || {};
      setEmbedProgress({
        embedded: statsPayload.embedded ?? 0,
        total: statsPayload.total_chunks ?? 0,
      });
      setEmbedRunning(status.running);
      const message =
        status.last_message ||
        (status.running
          ? "运行中…"
          : `完成（已嵌入 ${statsPayload.embedded ?? 0}/${statsPayload.total_chunks ?? statsPayload.embedded ?? 0}）`);
      setEmbedStatus(message);
      if (!status.running) {
        setEmbedJobId(null);
        if (status.returncode && status.returncode !== 0) {
          setEmbedError(`程序退出：code=${status.returncode}`);
        } else {
          setEmbedError(null);
        }
      }
      if (status.running) {
        setTimeout(() => pollEmbed(jid), 2000);
      }
    } catch (err) {
      setEmbedError(err instanceof Error ? err.message : "获取嵌入状态失败");
      setEmbedRunning(false);
    }
  };

  const pollSummarize = async (jid: string) => {
    try {
      const status = await getSummarizeStatus(settings, jid);
      setSummLog(status.log || "");
      const statsPayload = status.stats || {};
      const processedCount = statsPayload.processed_papers ?? statsPayload.processed ?? 0;
      const backendTotal = statsPayload.total_papers || statsPayload.papers_with_pdf || 0;
      const targetTotal =
        summTargetRef.current ??
        summTargetTotal ??
        (backendTotal || null) ??
        (processedCount || null);
      setSummProgress({
        processed: processedCount,
        total: targetTotal || backendTotal || processedCount || 0,
        errors: statsPayload.errors ?? 0,
        current_paper_title: statsPayload.current_paper_title,
      });
      setSummRunning(status.running);
      const message =
        status.last_message ||
        (status.running
          ? "运行中…"
          : `完成（已生成 ${processedCount}/${targetTotal || backendTotal || processedCount}）`);
      setSummStatus(message);
      if (!status.running) {
        setSummJobId(null);
        if (!summTargetRef.current && !summTargetTotal && processedCount > 0) {
          setSummTargetTotal(processedCount);
          summTargetRef.current = processedCount;
          setSummProgress((prev) => ({
            ...prev,
            total: processedCount,
          }));
        }
        if (!summaryFinishedNotified) {
          onSummaryFinished?.();
          setSummaryFinishedNotified(true);
        }
        fetchPipelineStats(settings)
          .then((data) => setStats(data))
          .catch((err) => console.warn("Failed to refresh stats after summarize", err));
        if (status.returncode && status.returncode !== 0) {
          setSummError(`程序退出：code=${status.returncode}`);
        } else {
          setSummError(null);
        }
        setSummRunning(false);
      }
      if (status.running) {
        setTimeout(() => pollSummarize(jid), 2000);
      }
    } catch (err) {
      setSummError(err instanceof Error ? err.message : "获取摘要状态失败");
      setSummRunning(false);
    }
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <div className="pill">PDF 切片</div>
        {running && (
          <div className="pill">
            运行中 {progress.processed_pdfs || 0}/{progress.total_pdfs || "?"}
          </div>
        )}
        {loading && <div className="pill">启动中…</div>}
        {progress.missing_files ? <div className="pill warn">缺失 {progress.missing_files}</div> : null}
      </div>
      {running || progress.total_pdfs ? (
        <div style={{ background: "#1f2937", borderRadius: 10, height: 10, overflow: "hidden", marginBottom: 8 }}>
          <div
            style={{
              width: `${progressPercent}%`,
              height: "100%",
              background: "linear-gradient(90deg, #8b5cf6, #22d3ee)",
              transition: "width 0.3s ease",
            }}
          />
        </div>
      ) : null}
      <div className="stack">
        <div className="stack-row">
          <label className="muted">chunk size</label>
          <input value={chunkSize} onChange={(e) => setChunkSize(e.target.value)} />
        </div>
        <div className="stack-row">
          <label className="muted">overlap</label>
          <input value={overlap} onChange={(e) => setOverlap(e.target.value)} />
        </div>
        <div className="stack-row">
          <label className="muted">limit（可选）</label>
          <input value={limit} onChange={(e) => setLimit(e.target.value)} />
        </div>
        <div className="stack-row">
          <label className="muted" style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input type="checkbox" checked={skipExistingChunks} onChange={(e) => setSkipExistingChunks(e.target.checked)} />
            跳过已有切片
          </label>
        </div>
        <button className="primary-btn" onClick={run} disabled={loading}>
          {loading ? "运行中…" : "运行 process_pdfs"}
        </button>
        {running && jobId && (
          <div className="stack-row">
            <button
              className="ghost-btn"
              onClick={async () => {
                try {
                  await stopProcessPdfs(settings, jobId);
                  setRunning(false);
                  setError(null);
                } catch (err) {
                  setError(err instanceof Error ? err.message : "停止失败");
                }
              }}
            >
              停止切片
            </button>
            <span className="muted">已处理 {progress.processed_pdfs || 0}/{progress.total_pdfs || "?"}</span>
          </div>
        )}

        <div className="stack-row">
          <button
            className="ghost-btn"
            onClick={async () => {
              setDedupeStatus("去重中…");
              try {
                const resp = await dedupeAttachments(settings);
                setDedupeStatus(`去重完成，删除 ${resp.result?.deleted ?? 0} 条重复附件`);
              } catch (err) {
                setDedupeStatus(err instanceof Error ? err.message : "去重失败");
              }
            }}
          >
            清理重复附件
          </button>
          {dedupeStatus && <span className="muted">{dedupeStatus}</span>}
        </div>

        <div className="pipeline-subsection">
          <div className="stack-row" style={{ gap: 8, alignItems: "center" }}>
            <label className="muted">Embedding model</label>
            <input
              style={{ maxWidth: 200 }}
              value={embedModel}
              onChange={(e) => setEmbedModel(e.target.value)}
              placeholder="如 text-embedding-3-large"
            />
            <label className="muted" style={{ minWidth: 90 }}>Limit（可选）</label>
            <input
              style={{ maxWidth: 120 }}
              value={embedProgress.total || ""}
              onChange={() => {}}
              disabled
              placeholder="自动"
              title="当前统计仅显示目标数"
            />
            <button
              className="ghost-btn"
              onClick={async () => {
                setEmbedStatus("启动嵌入…");
                setEmbedError(null);
                setEmbedProgress({});
                setEmbedLog("");
                try {
                  const resp = await startEmbedJob(settings, {
                    embed_model: embedModel || undefined,
                    batch_size: 16,
                  });
                  setEmbedJobId(resp.job_id);
                  setEmbedRunning(true);
                  setEmbedStatus(`已启动 job ${resp.job_id}`);
                  pollEmbed(resp.job_id);
                } catch (err) {
                  setEmbedStatus(err instanceof Error ? err.message : "触发失败");
                }
              }}
              disabled={embedRunning}
            >
              触发向量嵌入
            </button>
          </div>
          <div className="stack-row" style={{ gap: 12, flexWrap: "wrap" }}>
            {embedStatus && (
              <span className="pill" style={{ background: embedRunning ? "#1f2937" : "#334155" }}>
                {embedStatus}
              </span>
            )}
            {embedError && <span className="pill warn">{embedError}</span>}
          </div>
          {embedProgress.total ? (
            <>
              <div className="progress-track">
                <div className="progress-fill" style={{ width: `${embedPercent}%` }} />
              </div>
              <div className="summary-progress-meta">
                <span>
                  已嵌入 {embedProgress.embedded ?? 0}/{embedProgress.total}
                </span>
              </div>
            </>
          ) : embedRunning ? (
            <div className="muted">嵌入任务准备中…</div>
          ) : null}
          {embedLog && (
            <div className="summary-block" style={{ maxHeight: 160, overflow: "auto" }}>
              <h4>嵌入日志</h4>
              <div style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>
                {embedLog.split("\n").filter(Boolean).slice(-30).join("\n")}
              </div>
            </div>
          )}
        </div>

        <div className="pipeline-subsection">
          <div className="stack-row">
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <label className="muted">summary limit</label>
              <input style={{ maxWidth: 120 }} value={summLimit} onChange={(e) => setSummLimit(e.target.value)} />
              <label style={{ display: "flex", gap: 4, alignItems: "center" }}>
                <input type="checkbox" checked={summDryRun} onChange={(e) => setSummDryRun(e.target.checked)} />
                dry-run
              </label>
            </div>
            <button
              className="ghost-btn"
              onClick={async () => {
                setSummStatus("启动摘要…");
                setSummLog("");
                setSummProgress({});
                setSummError(null);
                setSummaryFinishedNotified(false);
                const limitValue = summLimit ? Number(summLimit) : undefined;
                if (limitValue) {
                  setSummTargetTotal(limitValue);
                  summTargetRef.current = limitValue;
                } else {
                  setSummTargetTotal(null);
                  summTargetRef.current = null;
                }
                const targetPromise = resolveSummaryTarget(limitValue);
                try {
                  const resp = await triggerSummarize(settings, {
                    limit: limitValue,
                    chunk_chars: 4000,
                    skip_existing: true,
                    dry_run: summDryRun,
                  });
                  setSummJobId(resp.job_id);
                  setSummRunning(true);
                  setSummStatus(`已启动 job ${resp.job_id}`);
                  pollSummarize(resp.job_id);
                  targetPromise
                    .then((value) => {
                      setSummTargetTotal(value);
                      summTargetRef.current = value ?? null;
                      setSummProgress((prev) => ({
                        ...prev,
                        total: value || prev.total || 0,
                      }));
                    })
                    .catch((err) => {
                      console.warn("Failed to fetch summary target", err);
                    });
                } catch (err) {
                  setSummStatus(err instanceof Error ? err.message : "触发失败");
                }
              }}
            >
              触发AI摘要/标签
            </button>
          </div>
          <div className="stack-row" style={{ gap: 12, flexWrap: "wrap" }}>
            {summStatus && (
              <span className="pill" style={{ background: summRunning ? "#1f2937" : "#334155" }}>
                {summStatus}
              </span>
            )}
            {summTargetTotal && (
              <span className="muted">本次计划处理 {summTargetTotal} 篇</span>
            )}
            {summError && <span className="pill warn">{summError}</span>}
          </div>
          {summProgress.total ? (
            <>
              <div className="progress-track">
                <div className="progress-fill" style={{ width: `${summPercent}%` }} />
              </div>
              <div className="summary-progress-meta">
                <span>
                  已生成 {summProgress.processed ?? 0}/{summProgress.total}
                </span>
                <span>错误 {summProgress.errors ?? 0}</span>
              </div>
            </>
          ) : summRunning ? (
            <div className="muted">摘要任务准备中…</div>
          ) : null}
          {summProgress.current_paper_title && (
            <div className="muted" style={{ fontSize: 13 }}>
              当前正在处理: {summProgress.current_paper_title}
            </div>
          )}
          {summRunning && (
            <div className="stack-row">
              <button
                className="ghost-btn"
                onClick={async () => {
                  if (!summJobId) return;
                  try {
                    await stopSummarize(settings, summJobId);
                    setSummRunning(false);
                    setSummStatus("已请求停止");
                  } catch (err) {
                    setSummStatus(err instanceof Error ? err.message : "停止失败");
                  }
                }}
              >
                停止摘要
              </button>
              <span className="muted">
                已处理 {summProgress.processed ?? 0}/{summProgress.total ?? "?"}，错误 {summProgress.errors ?? 0}
              </span>
            </div>
          )}
          {summLog && (
            <div className="summary-block" style={{ maxHeight: 160, overflow: "auto" }}>
              <h4>摘要日志</h4>
              <div style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>
                {summLog.split("\n").filter(Boolean).slice(-30).join("\n")}
              </div>
            </div>
          )}
        </div>

        <div className="stack-row">
          <button
            className="ghost-btn"
            onClick={async () => {
              try {
                setStatsError(null);
                const data = await fetchPipelineStats(settings);
                setStats(data);
              } catch (err) {
                setStatsError(err instanceof Error ? err.message : "获取统计失败");
              }
            }}
          >
            获取切片/摘要统计
          </button>
          {statsError && <span className="pill warn">{statsError}</span>}
        </div>

        {stats && (
          <div className="summary-block" style={{ maxHeight: 200, overflow: "auto" }}>
            <h4>统计</h4>
            <div style={{ display: "grid", gap: 4, fontSize: 13 }}>
              <span>PDF 总数: {stats.pdf_count}</span>
              <span>有 PDF 的论文数: {stats.papers_with_pdf}</span>
              <span>已有 chunk 的论文数: {stats.papers_with_chunks}</span>
              <span>缺少 chunk 的论文数: {stats.missing_papers}</span>
              <span>未切片的 PDF 数: {stats.missing_pdfs}</span>
              <span>已有摘要的论文数: {stats.papers_with_summary}</span>
              <span>缺少摘要的论文数: {stats.missing_summary}</span>
            </div>
            {stats.sample_missing?.length > 0 && (
              <div style={{ marginTop: 6 }}>
                <div className="muted">未切片示例（最多 20 条）：</div>
                <div style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>
                  {stats.sample_missing.map((m) => `${m.paper_id} | ${m.path}`).join("\n")}
                </div>
              </div>
            )}
          </div>
        )}
        {(output || stderr) && (
          <div className="summary-block" style={{ maxHeight: 220, overflow: "auto" }}>
            <h4>日志</h4>
            <div style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>
              {[...output.split("\n"), ...stderr.split("\n")]
                .filter(Boolean)
                .slice(-40)
                .join("\n")}
            </div>
          </div>
        )}
        {error && <div className="pill warn">{error}</div>}
      </div>
    </div>
  );
};
