import type { StepStatus } from "@/lib/domain/pipeline";
import { type Locale, getStatusLabel } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const statusStyles: Record<StepStatus, string> = {
  not_started: "bg-transparent text-[var(--muted-foreground)] ring-1 ring-[var(--border)]",
  generating: "bg-[#f4e7c9] text-[#72551d]",
  needs_review: "bg-[#eee1c3] text-[#6e5325]",
  approved: "bg-[#d8e6d4] text-[#2e5a3c]",
  needs_revision: "bg-[#f2d6ce] text-[#7b3a31]",
  blocked: "bg-[#ead7d2] text-[#75463a]",
  done: "bg-[#dbe5ea] text-[#345267]",
};

export function StatusBadge({
  status,
  className,
  locale = "en",
}: {
  status: StepStatus;
  className?: string;
  locale?: Locale;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em]",
        statusStyles[status],
        className,
      )}
    >
      {getStatusLabel(locale, status)}
    </span>
  );
}
