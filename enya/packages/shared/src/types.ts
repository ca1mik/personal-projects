export type JobType = "single-image" | "multi-view";
export type JobStatus = "queued" | "processing" | "done" | "failed" | "deleted";
export type FileCategory = "input" | "output";
export type ExecutionMode = "auto" | "stub" | "http" | "subprocess";

export interface StoredFile {
  role: string;
  category: FileCategory;
  filename: string;
  relative_path: string;
  content_type?: string | null;
  original_name?: string | null;
  size: number;
  created_at: string;
  url?: string | null;
}

export interface JobLogEntry {
  timestamp: string;
  level: "info" | "warning" | "error";
  message: string;
}

export interface JobErrorPayload {
  code: string;
  message: string;
}

export interface JobRecord {
  id: string;
  type: JobType;
  status: JobStatus;
  backend: string;
  created_at: string;
  updated_at: string;
  input_files: StoredFile[];
  output_files: StoredFile[];
  error?: JobErrorPayload | null;
  logs: JobLogEntry[];
  params: Record<string, unknown>;
  deleted_at?: string | null;
  rq_job_id?: string | null;
}

export interface JobsListData {
  items: JobRecord[];
}

export interface FilesData {
  input_files: StoredFile[];
  output_files: StoredFile[];
}

export interface ApiSuccess<T> {
  ok: true;
  data: T;
}

export interface ApiFailure {
  ok: false;
  error: {
    code: string;
    message: string;
  };
}

export type ApiResponse<T> = ApiSuccess<T> | ApiFailure;

