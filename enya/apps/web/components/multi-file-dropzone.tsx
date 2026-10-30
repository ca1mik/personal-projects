"use client";

import { useId, useState } from "react";

interface MultiFileDropzoneProps {
  label: string;
  hint: string;
  files: File[];
  onFilesChange: (files: File[]) => void;
}

function summarizeFiles(files: File[]): string {
  if (files.length === 0) {
    return "";
  }
  if (files.length === 1) {
    return `${files[0].name} | ${(files[0].size / 1024).toFixed(1)} KB`;
  }
  return `${files.length} files selected`;
}

export function MultiFileDropzone({ label, hint, files, onFilesChange }: MultiFileDropzoneProps) {
  const inputId = useId();
  const [dragging, setDragging] = useState(false);

  return (
    <label
      className={`dropzone multi-dropzone ${dragging ? "dragging" : ""} ${files.length > 0 ? "filled" : ""}`}
      htmlFor={inputId}
      onDragEnter={() => setDragging(true)}
      onDragLeave={() => setDragging(false)}
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        onFilesChange(Array.from(event.dataTransfer.files ?? []));
      }}
    >
      <input
        id={inputId}
        className="sr-only"
        type="file"
        accept="image/png,image/jpeg,image/webp"
        multiple
        onChange={(event) => onFilesChange(Array.from(event.currentTarget.files ?? []))}
      />
      <span className="dropzone-label">{label}</span>
      <span className="dropzone-hint">{files.length > 0 ? summarizeFiles(files) : hint}</span>
      <span className="dropzone-meta">
        {files.length > 0 ? "Click or drop to replace the whole set" : "PNG, JPG, or WEBP | multiple files"}
      </span>
      {files.length > 0 ? (
        <>
          <div className="multi-file-list">
            {files.slice(0, 6).map((file) => (
              <span key={`${file.name}-${file.size}`} className="mini-pill">
                {file.name}
              </span>
            ))}
            {files.length > 6 ? <span className="mini-pill">+{files.length - 6} more</span> : null}
          </div>
          <button
            className="ghost-button dropzone-clear"
            type="button"
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onFilesChange([]);
            }}
          >
            Clear set
          </button>
        </>
      ) : null}
    </label>
  );
}
