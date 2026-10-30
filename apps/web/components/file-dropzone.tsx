"use client";

import { useId, useState } from "react";

interface FileDropzoneProps {
  label: string;
  hint: string;
  file: File | null;
  required?: boolean;
  onFileChange: (file: File | null) => void;
}

export function FileDropzone({ label, hint, file, required = false, onFileChange }: FileDropzoneProps) {
  const inputId = useId();
  const [dragging, setDragging] = useState(false);

  return (
    <label
      className={`dropzone ${dragging ? "dragging" : ""} ${file ? "filled" : ""}`}
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
        const nextFile = event.dataTransfer.files?.[0] ?? null;
        onFileChange(nextFile);
      }}
    >
      <input
        id={inputId}
        className="sr-only"
        type="file"
        accept="image/png,image/jpeg,image/webp"
        required={required}
        onChange={(event) => onFileChange(event.currentTarget.files?.[0] ?? null)}
      />
      <span className="dropzone-label">{label}</span>
      <span className="dropzone-hint">{file ? `${file.name} | ${(file.size / 1024).toFixed(1)} KB` : hint}</span>
      <span className="dropzone-meta">{file ? "Click or drop to replace" : "PNG, JPG, or WEBP"}</span>
      {file ? (
        <button
          className="ghost-button dropzone-clear"
          type="button"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onFileChange(null);
          }}
        >
          Remove
        </button>
      ) : null}
    </label>
  );
}
