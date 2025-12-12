import React, { useRef, useState } from "react";
import { uploadCsv } from "../api";
import { Settings } from "../types";

interface Props {
  settings: Settings;
  onUploaded: () => void;
}

export const CsvUploader: React.FC<Props> = ({ settings, onUploaded }) => {
  const fileInput = useRef<HTMLInputElement | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [limit, setLimit] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    setSelectedFile(file || null);
    setError(null);
    setStatus("");
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError("Please select a CSV file");
      return;
    }
    setLoading(true);
    setError(null);
    setStatus("Uploading...");
    try {
      const result = await uploadCsv(settings, selectedFile, limit ? Number(limit) : undefined);
      setStatus(
        `Import complete: ${result.inserted} added, ${result.skipped} skipped, ${result.total_rows} total rows${
          result.non_papers?.length ? `, ${result.non_papers.length} non-paper items` : ""
        }`
      );
      if (result.non_papers?.length) {
        setError(
          `Detected non-paper types: ${result.non_papers
            .map((n: any) => n.item_type || "unknown")
            .join(", ")}`
        );
      }
      onUploaded();
      setSelectedFile(null);
      if (fileInput.current) fileInput.current.value = "";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setStatus("");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="stack">
      <div className="file-upload-wrapper">
        <input
          ref={fileInput}
          type="file"
          accept=".csv,text/csv"
          onChange={handleFileSelect}
          id="csv-file-input"
        />
        <label htmlFor="csv-file-input" className="file-upload-label">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M10 4V16M4 10H16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <span>{selectedFile ? selectedFile.name : "Choose CSV file"}</span>
        </label>
      </div>

      <div className="settings-row">
        <label>Limit (optional)</label>
        <input
          value={limit}
          onChange={(e) => setLimit(e.target.value)}
          placeholder="Leave empty to import all"
          disabled={loading}
        />
      </div>

      <button className="primary-btn" onClick={handleUpload} disabled={loading || !selectedFile}>
        {loading ? "Uploading..." : "Upload & Import"}
      </button>

      {status && <div className="success-banner">{status}</div>}
      {error && <div className="error-banner">{error}</div>}
      
      <p className="muted" style={{ fontSize: 12 }}>
        Files are processed locally on the backend, not uploaded externally.
      </p>
    </div>
  );
};
