import React from "react";

interface Props {
  query: string;
  itemType: string;
  onQueryChange: (value: string) => void;
  onItemTypeChange: (value: string) => void;
  onSubmit: () => void;
  loading?: boolean;
}

export const SearchBar: React.FC<Props> = ({
  query,
  itemType,
  onQueryChange,
  onItemTypeChange,
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
      <button className="primary-btn" onClick={onSubmit} disabled={loading}>
        {loading ? "Searching..." : "Search"}
      </button>
    </div>
  );
};
