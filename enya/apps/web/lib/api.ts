import type { ApiResponse, FilesData, JobRecord, JobsListData, StoredFile } from "@enya/shared";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

function apiUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      ...init,
      cache: "no-store"
    });
  } catch (error) {
    const target = apiUrl(path);
    if (error instanceof TypeError) {
      throw new Error(`Cannot reach API at ${target}. Start the FastAPI service on port 8000 and try again.`);
    }
    throw error;
  }

  let payload: ApiResponse<T>;
  try {
    payload = (await response.json()) as ApiResponse<T>;
  } catch {
    throw new Error(`Unexpected response from API (${response.status}).`);
  }

  if (!response.ok || !payload.ok) {
    throw new Error(payload.ok ? `API request failed (${response.status}).` : payload.error.message);
  }

  return payload.data;
}

export function assetUrl(
  file: Pick<StoredFile, "url" | "size" | "created_at"> | null | undefined
): string | null {
  if (!file?.url) {
    return null;
  }
  const target = new URL(apiUrl(file.url));
  target.searchParams.set("v", `${file.created_at ?? ""}-${file.size ?? 0}`);
  return target.toString();
}

export function findGlbFile(job: JobRecord | null | undefined): StoredFile | undefined {
  const glbFiles = job?.output_files.filter((file) => file.filename.toLowerCase().endsWith(".glb")) ?? [];
  return (
    glbFiles.find((file) => file.filename.toLowerCase() === "rigged.glb") ??
    glbFiles.find((file) => file.filename.toLowerCase() === "model.glb") ??
    glbFiles[0]
  );
}

export async function fetchJobs(): Promise<JobRecord[]> {
  const data = await requestJson<JobsListData>("/api/jobs");
  return data.items;
}

export async function fetchJob(jobId: string): Promise<JobRecord> {
  return requestJson<JobRecord>(`/api/jobs/${jobId}`);
}

export async function fetchJobFiles(jobId: string): Promise<FilesData> {
  return requestJson<FilesData>(`/api/jobs/${jobId}/files`);
}

export async function createSingleImageJob(payload: FormData): Promise<JobRecord> {
  return requestJson<JobRecord>("/api/jobs/single-image", {
    method: "POST",
    body: payload
  });
}

export async function createMultiViewJob(payload: FormData): Promise<JobRecord> {
  return requestJson<JobRecord>("/api/jobs/multi-view", {
    method: "POST",
    body: payload
  });
}

export async function rerunJob(jobId: string): Promise<JobRecord> {
  return requestJson<JobRecord>(`/api/jobs/${jobId}/rerun`, {
    method: "POST"
  });
}
