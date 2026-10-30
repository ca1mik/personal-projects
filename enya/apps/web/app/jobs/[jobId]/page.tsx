import { JobDetailClient } from "@/components/job-detail-client";


export const dynamic = "force-dynamic";


export default function JobDetailPage({ params }: { params: { jobId: string } }) {
  return <JobDetailClient jobId={params.jobId} />;
}

