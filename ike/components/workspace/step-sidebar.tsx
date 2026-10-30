import Link from "next/link";
import { Panel } from "@/components/ui/panel";
import { StatusBadge } from "@/components/ui/status-badge";
import type { ProjectWorkspace } from "@/lib/data/repository";
import type { StepId } from "@/lib/domain/pipeline";
import { type Locale, getStepLabel, withLang } from "@/lib/i18n";
import { cn } from "@/lib/utils";

// Small dot indicator per step
const stepDot: Record<string, string> = {
  not_started: "bg-[var(--border)]",
  generating: "bg-amber-400 animate-pulse",
  needs_review: "bg-amber-500",
  approved: "bg-emerald-500",
  needs_revision: "bg-red-400",
  blocked: "bg-red-500",
  done: "bg-emerald-600",
};

export function StepSidebar({
  workspace,
  activeStep,
  locale,
}: {
  workspace: ProjectWorkspace;
  activeStep: StepId;
  locale: Locale;
}) {
  return (
    <Panel className="p-0 overflow-hidden">
      {/* Header */}
      <div className="border-b border-[var(--border)] px-4 py-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
          {locale === "ru" ? "Шаги пайплайна" : "Pipeline Steps"}
        </p>
        <h2 className="mt-1.5 text-base font-semibold text-[var(--foreground)] leading-5 line-clamp-2">
          {workspace.project.title}
        </h2>
      </div>

      {/* Steps list */}
      <nav className="grid">
        {workspace.steps.map((step, index) => {
          const enabled =
            Boolean(step.latestArtifact) ||
            workspace.project.currentStepName === step.id ||
            index === 0;
          const isActive = activeStep === step.id;

          return (
            <Link
              key={step.id}
              href={
                enabled
                  ? withLang(`/projects/${workspace.project.id}?step=${step.id}`, locale)
                  : "#"
              }
              className={cn(
                "group border-b border-[var(--border)] px-4 py-3 transition-colors last:border-b-0 flex items-center gap-3",
                isActive && "bg-[var(--panel-strong)]",
                enabled ? "hover:bg-[var(--panel-strong)]" : "cursor-not-allowed opacity-45"
              )}
            >
              {/* Step number bubble */}
              <div
                className={cn(
                  "shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold transition-colors",
                  isActive
                    ? "bg-[var(--accent)] text-white"
                    : "bg-[var(--background)] text-[var(--muted-foreground)]"
                )}
              >
                {index + 1}
              </div>

              {/* Label + status dot */}
              <div className="flex-1 min-w-0">
                <p
                  className={cn(
                    "text-sm font-medium leading-5 truncate",
                    isActive ? "text-[var(--foreground)]" : "text-[var(--muted-foreground)]"
                  )}
                >
                  {getStepLabel(locale, step.id)}
                </p>
              </div>

              {/* Status dot */}
              <span
                className={cn(
                  "shrink-0 w-2 h-2 rounded-full",
                  stepDot[step.status] ?? stepDot.not_started
                )}
              />
            </Link>
          );
        })}
      </nav>
    </Panel>
  );
}
