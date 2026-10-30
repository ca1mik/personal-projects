"use client";

import { startTransition, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import type { JobRecord, StoredFile } from "@enya/shared";

import { CopyButton } from "@/components/copy-button";
import { JobHistory } from "@/components/job-history";
import { ModelViewerPanel } from "@/components/model-viewer-panel";
import { StatusBadge } from "@/components/status-badge";
import { assetUrl, fetchJob, fetchJobs, findGlbFile, rerunJob } from "@/lib/api";
import { formatBytes, formatTimestamp, titleCase } from "@/lib/format";

function groupInputFiles(files: StoredFile[]) {
  return {
    canonical: files.filter((file) => ["front", "left", "back", "right"].includes(file.role)),
    bodyExtras: files.filter((file) => file.role.startsWith("body-extra-")),
    faceReferences: files.filter((file) => file.role.startsWith("face-reference-")),
    other: files.filter(
      (file) =>
        !["front", "left", "back", "right"].includes(file.role) &&
        !file.role.startsWith("body-extra-") &&
        !file.role.startsWith("face-reference-"),
    )
  };
}

function InputFileSection({
  title,
  files
}: {
  title: string;
  files: StoredFile[];
}) {
  if (files.length === 0) {
    return null;
  }

  return (
    <div className="input-section">
      <div className="input-section-head">
        <strong>{title}</strong>
        <span>{files.length} files</span>
      </div>
      <div className="thumbnail-grid">
        {files.map((file) => (
          <figure key={file.filename} className="thumb-card">
            <img alt={file.role} src={assetUrl(file) ?? ""} />
            <figcaption>
              <strong>{titleCase(file.role)}</strong>
              <span>{file.filename}</span>
            </figcaption>
          </figure>
        ))}
      </div>
    </div>
  );
}

export function JobDetailClient({ jobId }: { jobId: string }) {
  const router = useRouter();
  const [job, setJob] = useState<JobRecord | null>(null);
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [rerunning, setRerunning] = useState(false);

  useEffect(() => {
    let mounted = true;

    async function load() {
      try {
        const [jobDetail, history] = await Promise.all([fetchJob(jobId), fetchJobs()]);
        if (mounted) {
          setJob(jobDetail);
          setJobs(history);
          setError(null);
        }
      } catch (nextError) {
        if (mounted) {
          setError(nextError instanceof Error ? nextError.message : "Failed to load job details.");
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    void load();
    const intervalId = window.setInterval(() => {
      void load();
    }, 3000);

    return () => {
      mounted = false;
      window.clearInterval(intervalId);
    };
  }, [jobId]);

  async function handleRerun() {
    setRerunning(true);
    setActionError(null);
    try {
      const nextJob = await rerunJob(jobId);
      setJob(nextJob);
      const nextHistory = await fetchJobs();
      setJobs(nextHistory);
      startTransition(() => router.refresh());
    } catch (nextError) {
      setActionError(nextError instanceof Error ? nextError.message : "Failed to rerun the job.");
    } finally {
      setRerunning(false);
    }
  }

  const groupedInputs = useMemo(() => groupInputFiles(job?.input_files ?? []), [job?.input_files]);
  const currentRunLogs = useMemo(() => {
    const logs = job?.logs ?? [];
    let startIndex = -1;
    for (let index = logs.length - 1; index >= 0; index -= 1) {
      if (logs[index]?.message === "Job reset for rerun." || logs[index]?.message.startsWith("Worker started processing")) {
        startIndex = index;
        break;
      }
    }
    return startIndex >= 0 ? logs.slice(startIndex) : logs;
  }, [job?.logs]);
  const glbFile = findGlbFile(job);
  const isStubJob =
    (job?.params.execution_mode ?? "auto") === "stub" ||
    currentRunLogs.some((entry) => entry.message.toLowerCase().includes("stub executed")) ||
    (glbFile?.size ?? 0) > 0 && (glbFile?.size ?? 0) < 5000;

  if (loading) {
    return (
      <div className="detail-shell">
        <div className="card empty-state">
          <p>Loading job...</p>
          <span>Reading metadata from local storage and polling the API.</span>
        </div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="detail-shell">
        <div className="card empty-state">
          <p>Job unavailable</p>
          <span>{error ?? "This job could not be loaded."}</span>
          <Link className="ghost-button" href="/">
            Back to studio
          </Link>
        </div>
      </div>
    );
  }
  return (
    <div className="detail-shell">
      <Link className="back-link" href="/">
        Back to studio
      </Link>

      <section className="card detail-header">
        <div>
          <p className="eyebrow">Job Detail</p>
          <h1 className="detail-title">{titleCase(job.type)} pipeline</h1>
          <div className="detail-meta-line">
            <StatusBadge status={job.status} />
            <span className="mono-tight">{job.id}</span>
          </div>
        </div>
        <div className="detail-actions">
          <CopyButton value={job.id} />
          <button className="primary-button" disabled={rerunning} type="button" onClick={handleRerun}>
            {rerunning ? "Queueing rerun..." : "Rerun job"}
          </button>
        </div>
      </section>

      {actionError ? (
        <div className="notice error-notice">
          <strong>Action failed</strong>
          <p>{actionError}</p>
        </div>
      ) : null}

      {job.error ? (
        <div className="notice error-notice">
          <strong>{job.error.code}</strong>
          <p>{job.error.message}</p>
        </div>
      ) : null}

      {isStubJob ? (
        <div className="notice error-notice">
          <strong>Stub output</strong>
          <p>
            This result is a placeholder preview from stub mode, not a real mesh generated from your photos.
            Switch the backend to a real local model runtime before judging quality.
          </p>
        </div>
      ) : null}

      <div className="detail-grid">
        <div className="detail-main">
          <section className="card viewer-card">
            <div className="section-header">
              <div>
                <p className="eyebrow">Preview</p>
                <h2>Browser mesh preview</h2>
              </div>
            </div>
            <ModelViewerPanel alt={`3D preview for job ${job.id}`} src={assetUrl(glbFile)} />
            <div className="download-row">
              {job.output_files.map((file) => (
                <a key={file.filename} className="ghost-button" download href={assetUrl(file) ?? "#"}>
                  Download {file.filename}
                </a>
              ))}
            </div>
          </section>

          <section className="card">
            <div className="section-header">
              <div>
                <p className="eyebrow">Inputs</p>
                <h2>Uploaded capture set</h2>
              </div>
            </div>
            <div className="capture-summary">
              <span className="mini-pill">Canonical body views: {groupedInputs.canonical.length}</span>
              <span className="mini-pill">Extra body references: {groupedInputs.bodyExtras.length}</span>
              <span className="mini-pill">Face references: {groupedInputs.faceReferences.length}</span>
            </div>
            <div className="input-sections">
              <InputFileSection files={groupedInputs.canonical} title="Canonical body views" />
              <InputFileSection files={groupedInputs.bodyExtras} title="Extra body references" />
              <InputFileSection files={groupedInputs.faceReferences} title="Face references" />
              <InputFileSection files={groupedInputs.other} title="Other inputs" />
            </div>
          </section>

          <section className="card">
            <div className="section-header">
              <div>
                <p className="eyebrow">Logs</p>
                <h2>Worker timeline</h2>
              </div>
            </div>
            <div className="log-list">
              {job.logs.map((entry, index) => (
                <div key={`${entry.timestamp}-${index}`} className={`log-entry log-${entry.level}`}>
                  <span className="mono-tight">{formatTimestamp(entry.timestamp)}</span>
                  <p>{entry.message}</p>
                </div>
              ))}
            </div>
          </section>
        </div>

        <aside className="side-column">
          <section className="card">
            <div className="section-header">
              <div>
                <p className="eyebrow">Metadata</p>
                <h2>Job record</h2>
              </div>
            </div>
            <div className="meta-grid">
              <div>
                <span>Backend</span>
                <strong>{job.backend}</strong>
              </div>
              <div>
                <span>Created</span>
                <strong>{formatTimestamp(job.created_at)}</strong>
              </div>
              <div>
                <span>Updated</span>
                <strong>{formatTimestamp(job.updated_at)}</strong>
              </div>
              <div>
                <span>Mode</span>
                <strong>{String(job.params.execution_mode ?? "auto")}</strong>
              </div>
              <div>
                <span>Stored inputs</span>
                <strong>{job.input_files.length}</strong>
              </div>
              <div>
                <span>Outputs</span>
                <strong>{job.output_files.length}</strong>
              </div>
            </div>
          </section>

          <section className="card">
            <div className="section-header">
              <div>
                <p className="eyebrow">Files</p>
                <h2>Output manifest</h2>
              </div>
            </div>
            <div className="file-list">
              {job.output_files.length === 0 ? (
                <div className="empty-state compact">
                  <p>No outputs yet.</p>
                  <span>Queued and processing jobs will populate this list when the worker finishes.</span>
                </div>
              ) : (
                job.output_files.map((file) => (
                  <div key={file.filename} className="file-row">
                    <div>
                      <strong>{file.filename}</strong>
                      <span>
                        {titleCase(file.role)} | {formatBytes(file.size)}
                      </span>
                    </div>
                    <a className="ghost-button" download href={assetUrl(file) ?? "#"}>
                      Download
                    </a>
                  </div>
                ))
              )}
            </div>
          </section>

          <JobHistory activeJobId={job.id} jobs={jobs} />
        </aside>
      </div>
    </div>
  );
}
