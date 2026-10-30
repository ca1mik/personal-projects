import { createProjectFromCandidateAction } from "@/app/actions";
import { Panel } from "@/components/ui/panel";
import { SubmitButton } from "@/components/ui/submit-button";
import type { TopicCandidate } from "@/lib/domain/pipeline";
import { type Locale, getDecisionLabel, getEffortLabel, getTopicStatusLabel, t, withLang } from "@/lib/i18n";
import { cn, formatRelative } from "@/lib/utils";

const statusTone: Record<TopicCandidate["status"], string> = {
  hot: "bg-[#d8e6d4] text-[#2e5a3c]",
  watch: "bg-[#eee1c3] text-[#6e5325]",
  commissioned: "bg-[#dbe5ea] text-[#345267]",
  cooling: "bg-[#ead7d2] text-[#75463a]",
};

export function TopicCandidateCard({
  candidate,
  locale,
}: {
  candidate: TopicCandidate;
  locale: Locale;
}) {
  return (
    <Panel className="flex h-full flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
            {t(locale, "topicCandidate")}
          </p>
          <h3 className="mt-2 text-xl font-semibold text-[var(--foreground)]">{candidate.title}</h3>
        </div>
        <span className={cn("rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em]", statusTone[candidate.status])}>
          {getTopicStatusLabel(locale, candidate.status)}
        </span>
      </div>

      <p className="text-sm leading-6 text-[var(--muted-foreground)]">{candidate.summary}</p>

      <div className="rounded-[22px] bg-[var(--background)] p-4">
        <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{t(locale, "recommendedAngle")}</p>
        <p className="mt-2 text-sm leading-6 text-[var(--foreground)]">{candidate.angle}</p>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-2xl bg-[var(--background)] p-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{t(locale, "youtubePotential")}</p>
          <p className="mt-1 text-2xl font-semibold text-[var(--foreground)]">{candidate.youtubePotentialScore}</p>
        </div>
        <div className="rounded-2xl bg-[var(--background)] p-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{t(locale, "momentum")}</p>
          <p className="mt-1 text-2xl font-semibold text-[var(--foreground)]">{candidate.momentumScore}</p>
        </div>
        <div className="rounded-2xl bg-[var(--background)] p-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{t(locale, "evidence")}</p>
          <p className="mt-1 text-2xl font-semibold text-[var(--foreground)]">{candidate.evidenceStrength}</p>
        </div>
        <div className="rounded-2xl bg-[var(--background)] p-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{t(locale, "novelty")}</p>
          <p className="mt-1 text-2xl font-semibold text-[var(--foreground)]">{candidate.noveltyScore}</p>
        </div>
        <div className="rounded-2xl bg-[var(--background)] p-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{t(locale, "virality")}</p>
          <p className="mt-1 text-2xl font-semibold text-[var(--foreground)]">{candidate.viralityScore}</p>
        </div>
        <div className="rounded-2xl bg-[var(--background)] p-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{t(locale, "competition")}</p>
          <p className="mt-1 text-2xl font-semibold text-[var(--foreground)]">{candidate.competitionPressure}</p>
        </div>
        <div className="rounded-2xl bg-[var(--background)] p-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{t(locale, "competitorLift")}</p>
          <p className="mt-1 text-2xl font-semibold text-[var(--foreground)]">{candidate.competitorMomentumScore}</p>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded-[22px] bg-[var(--background)] p-4">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{t(locale, "decision")}</p>
          <p className="mt-2 text-sm font-semibold uppercase tracking-[0.14em] text-[var(--foreground)]">
            {getDecisionLabel(locale, candidate.decision)}
          </p>
          <p className="mt-2 text-sm leading-6 text-[var(--muted-foreground)]">
            {t(locale, "window")}: {candidate.timingWindowDays} {t(locale, "days")}
          </p>
          <p className="mt-1 text-sm leading-6 text-[var(--muted-foreground)]">
            {t(locale, "effort")}: {getEffortLabel(locale, candidate.productionEffort)}
          </p>
        </div>
        <div className="rounded-[22px] bg-[var(--background)] p-4">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{t(locale, "unitEconomics")}</p>
          <p className="mt-2 text-sm leading-6 text-[var(--foreground)]">
            {t(locale, "cost")}: ${candidate.economics.totalCostUsd}
          </p>
          <p className="text-sm leading-6 text-[var(--muted-foreground)]">
            {t(locale, "breakEven")}: ~{candidate.economics.breakEvenViews.toLocaleString()} {t(locale, "views")}
          </p>
          <p className="text-sm leading-6 text-[var(--muted-foreground)]">
            {t(locale, "monetizationFit")}: {candidate.monetizationFitScore}
          </p>
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{t(locale, "whyNow")}</p>
        <p className="text-sm leading-6 text-[var(--foreground)]">{candidate.whyNow}</p>
        <p className="text-xs text-[var(--muted-foreground)]">{t(locale, "updatedLabel")} {formatRelative(candidate.updatedAt, locale)}</p>
      </div>

      <div className="rounded-[22px] bg-[var(--background)] p-4">
        <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{t(locale, "packagingHooks")}</p>
        <div className="mt-3 space-y-2">
          {candidate.packagingHooks.map((hook) => (
            <p key={hook} className="text-sm leading-6 text-[var(--foreground)]">
              {hook}
            </p>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {candidate.tags.map((tag) => (
          <span
            key={tag}
            className="rounded-full bg-[var(--background)] px-3 py-1 text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--muted-foreground)]"
          >
            {tag}
          </span>
        ))}
      </div>

      <form action={createProjectFromCandidateAction} className="mt-auto">
        <input type="hidden" name="returnTo" value={withLang("/radar", locale)} />
        <input type="hidden" name="title" value={candidate.title} />
        <input type="hidden" name="topic" value={candidate.summary} />
        <input type="hidden" name="angle" value={candidate.angle} />
        <SubmitButton label={t(locale, "createProjectFromTopic")} pendingLabel={t(locale, "creating")} />
      </form>
    </Panel>
  );
}
