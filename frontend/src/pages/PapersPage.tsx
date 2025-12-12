import React, { useEffect, useState } from "react";
import { fetchPaperDetail, fetchPapers } from "../api";
import { SearchBar } from "../components/SearchBar";
import { PaperList } from "../components/PaperList";
import { PaperDetailPanel } from "../components/PaperDetail";
import { PaperDetail, PaperListItem, Settings } from "../types";

const PAGE_SIZE = 20;

interface PapersPageProps {
  settings: Settings;
}

export const PapersPage: React.FC<PapersPageProps> = ({ settings }) => {
  const [query, setQuery] = useState("");
  const [itemType, setItemType] = useState("");
  const [searchField, setSearchField] = useState("title_abstract");
  const [sortBy, setSortBy] = useState<"date" | "title">("date");
  const [sortOrder, setSortOrder] = useState<"desc" | "asc">("desc");
  const [papers, setPapers] = useState<PaperListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [listLoading, setListLoading] = useState(false);
  const [loadMoreLoading, setLoadMoreLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<PaperDetail | null>(null);

  const sortPapers = (items: PaperListItem[]) => {
    const sorted = [...items];
    if (sortBy === "date") {
      sorted.sort((a, b) => {
        const yearA = a.year || 0;
        const yearB = b.year || 0;
        return sortOrder === "desc" ? yearB - yearA : yearA - yearB;
      });
    } else if (sortBy === "title") {
      sorted.sort((a, b) => {
        const titleA = (a.title || "").toLowerCase();
        const titleB = (b.title || "").toLowerCase();
        return sortOrder === "asc" ? titleA.localeCompare(titleB) : titleB.localeCompare(titleA);
      });
    }
    return sorted;
  };

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
      const sortedPapers = sortPapers(resp.items);
      setPapers(sortedPapers);
      setTotal(resp.total);
      if (sortedPapers.length > 0) {
        setSelectedId(sortedPapers[0].id);
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
      const sortedNew = sortPapers(resp.items);
      setPapers((prev) => [...prev, ...sortedNew]);
      setTotal(resp.total);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Failed to load list");
    } finally {
      setLoadMoreLoading(false);
    }
  };

  useEffect(() => {
    if (papers.length > 0) {
      const sorted = sortPapers(papers);
      setPapers(sorted);
    }
  }, [sortBy, sortOrder]);

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

  useEffect(() => {
    runSearch();
  }, [settings.apiBase]);

  useEffect(() => {
    if (selectedId !== null) {
      loadDetail(selectedId);
    }
  }, [selectedId, settings.apiBase]);

  return (
    <div className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Paper Library</h1>
          <p className="page-subtitle">
            {query ? `Searching for "${query}"` : itemType ? `Type: ${itemType}` : `Total ${total} papers`}
          </p>
        </div>
        <button className="primary-btn" onClick={runSearch}>
          Refresh
        </button>
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

      <div className="filter-bar">
        <div className="filter-group">
          <label className="filter-label">Sort by:</label>
          <div className="button-group">
            <button
              className={`filter-btn ${sortBy === "date" ? "active" : ""}`}
              onClick={() => setSortBy("date")}
            >
              Date
            </button>
            <button
              className={`filter-btn ${sortBy === "title" ? "active" : ""}`}
              onClick={() => setSortBy("title")}
            >
              Title
            </button>
          </div>
        </div>
        <div className="filter-group">
          <label className="filter-label">Order:</label>
          <div className="button-group">
            <button
              className={`filter-btn ${sortOrder === "desc" ? "active" : ""}`}
              onClick={() => setSortOrder("desc")}
            >
              {sortBy === "date" ? "Newest" : "Z-A"}
            </button>
            <button
              className={`filter-btn ${sortOrder === "asc" ? "active" : ""}`}
              onClick={() => setSortOrder("asc")}
            >
              {sortBy === "date" ? "Oldest" : "A-Z"}
            </button>
          </div>
        </div>
        <div className="result-count">
          {total} papers
        </div>
      </div>

      {listError && <div className="error-banner">{listError}</div>}

      <div className="papers-layout">
        <div className="papers-list-section">
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
        </div>
        <div className="papers-detail-section">
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
        </div>
      </div>
    </div>
  );
};

