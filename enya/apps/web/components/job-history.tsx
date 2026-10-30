import Link from "next/link";

import type { JobRecord } from "@enya/shared";

import { formatTimestamp, titleCase } from "@/lib/format";
import { StatusBadge } from "@/components/status-badge";

interface JobHistoryProps {
  jobs: JobRecord[];
  activeJobId?: string;
}

export function JobHistory({ jobs, activeJobId }: JobHistoryProps) {
  return (
    <section className="card history-card">
      <div className="section-header">
        <div>
          <p className="eyebrow">Local History</p>
          <h2>Recent jobs</h2>
        </div>
        <p className="muted-copy">{jobs.length} stored locally</p>
      </div>

      {jobs.length === 0 ? (
        <div className="empty-state compact">
          <p>No jobs yet.</p>
          <span>Uploads, metadata, and outputs will appear here once you submit a run.</span>
        </div>
      ) : (
        <div className="history-list">
          {jobs.map((job) => (
            <Link
              key={job.id}
              className={`history-item ${job.id === activeJobId ? "active" : ""}`}
              href={`/jobs/${job.id}`}
            >
              <div className="history-head">
                <span className="mono-tight">{job.id.slice(0, 8)}</span>
                <StatusBadge status={job.status} />
              </div>
              <p>{titleCase(job.type)}</p>
              <div className="history-meta">
                <span>{job.backend}</span>
                <span>{formatTimestamp(job.updated_at)}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

