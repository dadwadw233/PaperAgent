import React from "react";

interface Props {
  query: string;
  itemType: string;
  searchField: string;
  onQueryChange: (value: string) => void;
  onItemTypeChange: (value: string) => void;
  onSearchFieldChange: (value: string) => void;
  onSubmit: () => void;
  loading?: boolean;
}

export const SearchBar: React.FC<Props> = ({
  query,
  itemType,
  searchField,
  onQueryChange,
  onItemTypeChange,
  onSearchFieldChange,
  onSubmit,
  loading,
}) => {
  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      onSubmit();
    }
  };

  return (
    <div className="search-bar">
      <input
        className="search-input"
        placeholder="Search title or abstract..."
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        onKeyDown={handleKey}
      />
      <select
        className="select-input"
        value={itemType}
        onChange={(e) => onItemTypeChange(e.target.value)}
      >
        <option value="">All types</option>
        <option value="journalArticle">Journal</option>
        <option value="conferencePaper">Conference</option>
        <option value="preprint">Preprint</option>
        <option value="report">Report</option>
        <option value="book">Book</option>
      </select>
      <select
        className="select-input"
        value={searchField}
        onChange={(e) => onSearchFieldChange(e.target.value)}
        title="选择检索字段"
      >
        <option value="title_abstract">标题+摘要</option>
        <option value="title">仅标题</option>
        <option value="abstract">仅摘要</option>
        <option value="summary_long">AI 摘要（长）</option>
        <option value="summary_one_liner">AI 摘要（一句话）</option>
        <option value="summary_snarky">AI 摘要（吐槽）</option>
        <option value="summary">AI 摘要（全部）</option>
      </select>
      <button className="primary-btn" onClick={onSubmit} disabled={loading}>
        {loading ? "Searching..." : "Search"}
      </button>
    </div>
  );
};
