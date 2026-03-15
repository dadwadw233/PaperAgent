import React from "react";

interface PageLoaderProps {
  title?: string;
  subtitle?: string;
}

export const PageLoader: React.FC<PageLoaderProps> = ({
  title = "Loading content",
  subtitle = "Preparing data for this page...",
}) => {
  return (
    <div className="page-loader" role="status" aria-live="polite">
      <div className="page-loader-card">
        <div className="page-loader-orbit" aria-hidden="true" />
        <div className="page-loader-dots" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <p className="page-loader-title">{title}</p>
        <p className="page-loader-subtitle">{subtitle}</p>
      </div>
    </div>
  );
};
