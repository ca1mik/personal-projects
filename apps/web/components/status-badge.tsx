import type { JobStatus } from "@enya/shared";

const LABELS: Record<JobStatus, string> = {
  queued: "Queued",
  processing: "Processing",
  done: "Done",
  failed: "Failed",
  deleted: "Deleted"
};

export function StatusBadge({ status }: { status: JobStatus }) {
  return <span className={`status-badge status-${status}`}>{LABELS[status]}</span>;
}

