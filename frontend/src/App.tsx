import React, { useEffect, useMemo, useState } from "react";
import { fetchPaperDetail, fetchPapers, fetchConfig, updateConfig } from "./api";
import { SearchBar } from "./components/SearchBar";
import { PaperList } from "./components/PaperList";
import { PaperDetailPanel } from "./components/PaperDetail";
import { ChatPanel } from "./components/ChatPanel";
import { SettingsPanel } from "./components/SettingsPanel";
import { loadSettings, saveSettings, defaultSettings } from "./storage";
import { PaperDetail, PaperListItem, Settings } from "./types";
import { CsvUploader } from "./components/CsvUploader";
import { PipelinePanel } from "./components/PipelinePanel";

const PAGE_SIZE = 20;

const App: React.FC = () => {
  const [settings, setSettings] = useState<Settings>(() => loadSettings());
  const [query, setQuery] = useState("");
  const [itemType, setItemType] = useState("");
  const [searchField, setSearchField] = useState("title_abstract");
  const [papers, setPapers] = useState<PaperListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [listLoading, setListLoading] = useState(false);
  const [loadMoreLoading, setLoadMoreLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<PaperDetail | null>(null);
  const [savingConfig, setSavingConfig] = useState(false);
  const [configError, setConfigError] = useState<string | null>(null);
  const [lastSynced, setLastSynced] = useState<string | null>(null);

  useEffect(() => {
    saveSettings(settings);
  }, [settings]);

  const listSubtitle = useMemo(() => {
    if (query) return `“${query}”`;
    if (itemType) return itemType;
    return "All papers";
  }, [query, itemType]);

  const runSearch = async () => {
    setListLoading(true);
    setListError(null);
    try {
      const resp = await fetchPapers(settings, {
        q: query || undefined,
        item_type: itemType || undefined,
        limit: PAGE_SIZE,
        offset: 0,
        search_fields: searchField || undefined,
      });
      setPapers(resp.items);
      setTotal(resp.total);
      if (resp.items.length > 0) {
        setSelectedId(resp.items[0].id);
      } else {
        setSelectedId(null);
        setDetail(null);
      }
      setLoadMoreLoading(false);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Failed to load list");
    } finally {
      setListLoading(false);
    }
  };

  const loadMore = async () => {
    if (loadMoreLoading || listLoading) return;
    if (papers.length >= total) return;
    setLoadMoreLoading(true);
    try {
      const resp = await fetchPapers(settings, {
        q: query || undefined,
        item_type: itemType || undefined,
        limit: PAGE_SIZE,
        offset: papers.length,
        search_fields: searchField || undefined,
      });
      setPapers((prev) => [...prev, ...resp.items]);
      setTotal(resp.total);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Failed to load list");
    } finally {
      setLoadMoreLoading(false);
    }
  };

  const loadDetail = async (id: number) => {
    setDetailLoading(true);
    setDetailError(null);
    try {
      const data = await fetchPaperDetail(settings, id);
      setDetail(data);
    } catch (err) {
      setDetailError(err instanceof Error ? err.message : "Failed to load paper");
    } finally {
      setDetailLoading(false);
    }
  };

  const refreshSelectedDetail = () => {
    if (selectedId !== null) {
      loadDetail(selectedId);
    }
  };

  useEffect(() => {
    runSearch();
  }, [settings.apiBase]);

  useEffect(() => {
    if (selectedId !== null) {
      loadDetail(selectedId);
    }
  }, [selectedId, settings.apiBase]);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        const cfg = await fetchConfig(settings);
        setSettings((prev) => ({
          ...prev,
          llmBaseUrl: cfg.LLM_BASE_URL || prev.llmBaseUrl,
          llmModel: cfg.LLM_MODEL || prev.llmModel,
          llmApiKey: cfg.LLM_API_KEY || prev.llmApiKey,
        }));
        setLastSynced(new Date().toLocaleTimeString());
        setConfigError(null);
      } catch (err) {
        setConfigError(err instanceof Error ? err.message : "Load config failed");
      }
    };
    loadConfig();
  }, [settings.apiBase]);

  const saveConfigToBackend = async () => {
    setSavingConfig(true);
    setConfigError(null);
    try {
      await updateConfig(settings, {
        LLM_BASE_URL: settings.llmBaseUrl,
        LLM_MODEL: settings.llmModel,
        LLM_API_KEY: settings.llmApiKey,
        EMBED_BASE_URL: settings.llmBaseUrl,
        EMBED_MODEL: settings.llmModel,
        EMBED_API_KEY: settings.llmApiKey,
      });
      setLastSynced(new Date().toLocaleTimeString());
    } catch (err) {
      setConfigError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSavingConfig(false);
    }
  };

  return (
    <div className="app-shell">
      <div className="top-bar">
        <div className="brand">
          <span role="img" aria-label="sparkles">
            ✨
          </span>
          <span>Paper Agent</span>
          <div className="pill">{listSubtitle}</div>
          {listError && <div className="pill warn">{listError}</div>}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="ghost-btn" onClick={() => runSearch()}>
            Refresh
          </button>
          <button className="ghost-btn" onClick={() => setSettings(defaultSettings)}>
            Reset settings
          </button>
        </div>
      </div>

      <SearchBar
        query={query}
        itemType={itemType}
        onQueryChange={setQuery}
        onItemTypeChange={setItemType}
        searchField={searchField}
        onSearchFieldChange={setSearchField}
        onSubmit={runSearch}
        loading={listLoading}
      />

      <div className="layout">
        <PaperList
          items={papers}
          total={total}
          loading={listLoading}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onLoadMore={loadMore}
          canLoadMore={!listLoading && papers.length < total}
          loadingMore={loadMoreLoading}
        />
        <PaperDetailPanel
          detail={detail}
          loading={detailLoading}
          error={detailError}
          settings={settings}
          onCleared={() => {
            if (selectedId) {
              loadDetail(selectedId);
            }
          }}
        />
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <CsvUploader settings={settings} onUploaded={runSearch} />
          <PipelinePanel settings={settings} onSummaryFinished={refreshSelectedDetail} />
          <ChatPanel paper={detail} settings={settings} />
          <SettingsPanel
            settings={settings}
            onChange={setSettings}
            onSave={saveConfigToBackend}
            saving={savingConfig}
            lastSynced={lastSynced}
            error={configError}
          />
        </div>
      </div>
    </div>
  );
};

export default App;
