import React, { useRef, useState } from "react";
import { uploadCsv } from "../api";
import { Settings } from "../types";

interface Props {
  settings: Settings;
  onUploaded: () => void;
}

export const CsvUploader: React.FC<Props> = ({ settings, onUploaded }) => {
  const fileInput = useRef<HTMLInputElement | null>(null);
  const [limit, setLimit] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleUpload = async () => {
    const file = fileInput.current?.files?.[0];
    if (!file) {
      setError("请选择一个 CSV 文件");
      return;
    }
    setLoading(true);
    setError(null);
    setStatus("上传中…");
    try {
      const result = await uploadCsv(settings, file, limit ? Number(limit) : undefined);
      setStatus(
        `导入完成：新增 ${result.inserted} 条，跳过 ${result.skipped} 条，总计 ${result.total_rows} 行${
          result.non_papers?.length ? `，非论文 ${result.non_papers.length} 条` : ""
        }`,
      );
      if (result.non_papers?.length) {
        setError(
          `检测到非论文类型（${result.non_papers
            .map((n: any) => n.item_type || "unknown")
            .join(", ")}），请确认是否需要保留。`,
        );
      }
      onUploaded();
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <div className="pill">上传 Zotero CSV</div>
        {loading && <div className="pill">处理中…</div>}
      </div>
      <div style={{ display: "grid", gap: 8 }}>
        <input ref={fileInput} type="file" accept=".csv,text/csv" />
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            style={{ maxWidth: 140 }}
            placeholder="limit（可选）"
            value={limit}
            onChange={(e) => setLimit(e.target.value)}
          />
          <button className="primary-btn" onClick={handleUpload} disabled={loading}>
            {loading ? "上传中…" : "上传并导入"}
          </button>
        </div>
        {status && <div className="pill info">{status}</div>}
        {error && <div className="pill warn">{error}</div>}
        <div className="muted">文件仅在后台解析，不会上传到外部。</div>
      </div>
    </div>
  );
};
