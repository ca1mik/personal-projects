"use client";

import { type FormEvent, startTransition, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import type { ExecutionMode, JobRecord } from "@enya/shared";

import { FileDropzone } from "@/components/file-dropzone";
import { JobHistory } from "@/components/job-history";
import { MultiFileDropzone } from "@/components/multi-file-dropzone";
import { createMultiViewJob, createSingleImageJob, fetchJobs } from "@/lib/api";

type StudioTab = "single" | "multi";

const EXECUTION_MODE_OPTIONS: { label: string; value: ExecutionMode; description: string }[] = [
  { label: "Auto", value: "auto", description: "Use the adapter default from .env." },
  { label: "Stub", value: "stub", description: "Generate deterministic local placeholder output." },
  { label: "HTTP", value: "http", description: "Call a separately running local backend service." },
  { label: "Subprocess", value: "subprocess", description: "Run a local CLI or Python script adapter." }
];

export function StudioHome() {
  const router = useRouter();
  const [tab, setTab] = useState<StudioTab>("single");
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [singleMode, setSingleMode] = useState<ExecutionMode>("auto");
  const [multiMode, setMultiMode] = useState<ExecutionMode>("auto");
  const [singleFile, setSingleFile] = useState<File | null>(null);
  const [frontFile, setFrontFile] = useState<File | null>(null);
  const [leftFile, setLeftFile] = useState<File | null>(null);
  const [backFile, setBackFile] = useState<File | null>(null);
  const [rightFile, setRightFile] = useState<File | null>(null);
  const [bodyExtras, setBodyExtras] = useState<File[]>([]);
  const [faceReferences, setFaceReferences] = useState<File[]>([]);
  const [submittingTab, setSubmittingTab] = useState<StudioTab | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function loadJobs() {
      try {
        const nextJobs = await fetchJobs();
        if (mounted) {
          setJobs(nextJobs);
          setHistoryError(null);
        }
      } catch (error) {
        if (mounted) {
          setHistoryError(error instanceof Error ? error.message : "Failed to load jobs.");
        }
      }
    }

    void loadJobs();
    const intervalId = window.setInterval(() => {
      void loadJobs();
    }, 4000);

    return () => {
      mounted = false;
      window.clearInterval(intervalId);
    };
  }, []);

  async function handleSingleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!singleFile) {
      setFormError("Add a single image before starting a single-image run.");
      return;
    }

    const payload = new FormData();
    payload.append("image", singleFile);
    payload.append("execution_mode", singleMode);

    setSubmittingTab("single");
    setFormError(null);

    try {
      const job = await createSingleImageJob(payload);
      setJobs((current) => [job, ...current.filter((entry) => entry.id !== job.id)]);
      startTransition(() => router.push(`/jobs/${job.id}`));
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Failed to create the job.");
    } finally {
      setSubmittingTab(null);
    }
  }

  async function handleMultiSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!frontFile || !leftFile || !backFile) {
      setFormError("Front, left, and back views are required for a multi-view run.");
      return;
    }

    const payload = new FormData();
    payload.append("front", frontFile);
    payload.append("left", leftFile);
    payload.append("back", backFile);
    if (rightFile) {
      payload.append("right", rightFile);
    }
    bodyExtras.forEach((file) => payload.append("body_extras", file));
    faceReferences.forEach((file) => payload.append("face_references", file));
    payload.append("execution_mode", multiMode);

    setSubmittingTab("multi");
    setFormError(null);

    try {
      const job = await createMultiViewJob(payload);
      setJobs((current) => [job, ...current.filter((entry) => entry.id !== job.id)]);
      startTransition(() => router.push(`/jobs/${job.id}`));
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Failed to create the job.");
    } finally {
      setSubmittingTab(null);
    }
  }

  const isSubmitting = submittingTab !== null;

  return (
    <div className="studio-shell">
      <section className="card hero-card">
        <div className="hero-copy">
          <p className="eyebrow">Enya Local 3D Studio</p>
          <h1>Local-first image-to-mesh generation with swappable backends.</h1>
          <p className="hero-summary">
            This MVP stores uploads, metadata, and generated artifacts under <code>./storage</code>, queues work in
            Redis/RQ, and keeps both the FastAPI gateway and the backend adapters ready for real model integration.
          </p>
        </div>
        <div className="hero-stats">
          <div className="stat-chip">
            <span className="stat-label">Storage</span>
            <strong>Inputs / Jobs / Outputs</strong>
          </div>
          <div className="stat-chip">
            <span className="stat-label">Queue</span>
            <strong>Redis + RQ</strong>
          </div>
          <div className="stat-chip">
            <span className="stat-label">Preview</span>
            <strong>GLB in browser</strong>
          </div>
        </div>
      </section>

      <div className="studio-grid">
        <section className="card composer-card">
          <div className="section-header">
            <div>
              <p className="eyebrow">Create Job</p>
              <h2>Choose your input flow</h2>
            </div>
            <span className="subtle-pill">{isSubmitting ? "Submitting..." : "Ready"}</span>
          </div>

          <div className="tab-row" role="tablist" aria-label="Generation modes">
            <button
              className={`tab-button ${tab === "single" ? "active" : ""}`}
              type="button"
              onClick={() => setTab("single")}
            >
              Single Image
            </button>
            <button
              className={`tab-button ${tab === "multi" ? "active" : ""}`}
              type="button"
              onClick={() => setTab("multi")}
            >
              Multi View
            </button>
          </div>

          {formError ? (
            <div className="notice error-notice">
              <strong>Unable to submit</strong>
              <p>{formError}</p>
            </div>
          ) : null}

          {tab === "single" ? (
            <form className="form-stack" onSubmit={handleSingleSubmit}>
              <div className="inline-field">
                <label htmlFor="single-mode">Adapter mode</label>
                <select
                  id="single-mode"
                  value={singleMode}
                  onChange={(event) => setSingleMode(event.target.value as ExecutionMode)}
                >
                  {EXECUTION_MODE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <p>{EXECUTION_MODE_OPTIONS.find((option) => option.value === singleMode)?.description}</p>
              </div>

              <FileDropzone
                label="Reference image"
                hint="Drop one product shot, sketch, or render"
                file={singleFile}
                required
                onFileChange={setSingleFile}
              />

              <div className="cta-row">
                <button className="primary-button" disabled={submittingTab === "single"} type="submit">
                  {submittingTab === "single" ? "Queueing..." : "Generate 3D Mesh"}
                </button>
                <p className="helper-copy">Routes to the `sf3d` adapter and returns a job id immediately.</p>
              </div>
            </form>
          ) : (
            <form className="form-stack" onSubmit={handleMultiSubmit}>
              <div className="inline-field">
                <label htmlFor="multi-mode">Adapter mode</label>
                <select
                  id="multi-mode"
                  value={multiMode}
                  onChange={(event) => setMultiMode(event.target.value as ExecutionMode)}
                >
                  {EXECUTION_MODE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <p>{EXECUTION_MODE_OPTIONS.find((option) => option.value === multiMode)?.description}</p>
              </div>

              <div className="dropzone-grid">
                <FileDropzone label="Front view" hint="Primary front shot" file={frontFile} required onFileChange={setFrontFile} />
                <FileDropzone label="Left view" hint="Required side view" file={leftFile} required onFileChange={setLeftFile} />
                <FileDropzone label="Back view" hint="Required back view" file={backFile} required onFileChange={setBackFile} />
                <FileDropzone label="Right view" hint="Optional extra view" file={rightFile} onFileChange={setRightFile} />
              </div>

              <div className="capture-reference-grid">
                <MultiFileDropzone
                  label="Body reference set"
                  hint="Add extra full-body angles from your 8-shot pose set"
                  files={bodyExtras}
                  onFilesChange={setBodyExtras}
                />
                <MultiFileDropzone
                  label="Face reference set"
                  hint="Add close facial angles from your 8-shot face set"
                  files={faceReferences}
                  onFilesChange={setFaceReferences}
                />
              </div>

              <div className="capture-note">
                <strong>Doll workflow</strong>
                <p>
                  Use front, left, back, and optional right as canonical body views. Extra body and face images are
                  stored with the job for future texture or likeness refinement.
                </p>
              </div>

              <div className="cta-row">
                <button className="primary-button" disabled={submittingTab === "multi"} type="submit">
                  {submittingTab === "multi" ? "Queueing..." : "Generate Multi-View Mesh"}
                </button>
                <p className="helper-copy">
                  Routes to the `hunyuan_mv` adapter with canonical body views while preserving your extra body and face
                  references locally.
                </p>
              </div>
            </form>
          )}
        </section>

        <aside className="side-column">
          <section className="card notes-card">
            <div className="section-header">
              <div>
                <p className="eyebrow">Pipeline Notes</p>
                <h2>MVP behavior</h2>
              </div>
            </div>
            <div className="notes-list">
              <p>Jobs are stored locally as JSON metadata and filesystem assets.</p>
              <p>Stub mode generates previewable GLB and OBJ files so the full product works end-to-end.</p>
              <p>Multi-view jobs can now keep canonical body shots plus extra body and face reference sets.</p>
              <p>HTTP and subprocess modes are ready for real Stable Fast 3D and Hunyuan3D-2mv hookups.</p>
            </div>
          </section>

          {historyError ? (
            <div className="notice error-notice">
              <strong>History unavailable</strong>
              <p>{historyError}</p>
            </div>
          ) : null}

          <JobHistory jobs={jobs} />
        </aside>
      </div>
    </div>
  );
}
