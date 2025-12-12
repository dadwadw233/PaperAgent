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
      e.preventDefault();
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
        title="Search fields"
      >
        <option value="title_abstract">Title + Abstract</option>
        <option value="title">Title only</option>
        <option value="abstract">Abstract only</option>
        <option value="authors">Authors</option>
        <option value="summary_long">AI Summary (Long)</option>
        <option value="summary_one_liner">AI Summary (One-liner)</option>
        <option value="summary_snarky">AI Summary (Snarky)</option>
        <option value="summary">AI Summary (All)</option>
      </select>
      <button className="primary-btn" onClick={onSubmit} disabled={loading}>
        {loading ? "Searching..." : "Search"}
      </button>
    </div>
  );
};
