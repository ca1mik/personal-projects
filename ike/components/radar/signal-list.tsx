import { Panel } from "@/components/ui/panel";
import type { CompetitorVideoSignal, NewsRadarSource, NewsSignal, TopicCandidate } from "@/lib/domain/pipeline";
import { type Locale, getPerformanceBandLabel, t } from "@/lib/i18n";
import { formatDateTime, formatRelative } from "@/lib/utils";

export function SourceList({ sources, locale }: { sources: NewsRadarSource[]; locale: Locale }) {
  return (
    <Panel>
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
        {t(locale, "curatedSources")}
      </p>
      <div className="mt-4 space-y-3">
        {sources.map((source) => (
          <div key={source.id} className="rounded-2xl bg-[var(--background)] p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-[var(--foreground)]">{source.label}</p>
              <span className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">
                {source.category}
              </span>
            </div>
            <p className="mt-1 text-xs text-[var(--muted-foreground)]">{source.region}</p>
          </div>
        ))}
      </div>
    </Panel>
  );
}

export function NewsSignalList({ signals, locale }: { signals: NewsSignal[]; locale: Locale }) {
  return (
    <Panel>
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
        {t(locale, "rawSignals")}
      </p>
      <div className="mt-4 space-y-3">
        {signals.map((signal) => (
          <a
            key={signal.id}
            href={signal.url}
            target="_blank"
            rel="noreferrer"
            className="block rounded-2xl bg-[var(--background)] p-3 transition-colors hover:bg-white"
          >
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-[var(--foreground)]">{signal.sourceLabel}</p>
              <p className="text-xs text-[var(--muted-foreground)]">{formatDateTime(signal.publishedAt, locale)}</p>
            </div>
            <p className="mt-2 text-sm leading-6 text-[var(--foreground)]">{signal.title}</p>
            <p className="mt-2 text-sm leading-6 text-[var(--muted-foreground)]">{signal.summary}</p>
            <p className="mt-2 text-xs text-[var(--muted-foreground)]">{t(locale, "cluster")}: {signal.clusterKey}</p>
          </a>
        ))}
      </div>
    </Panel>
  );
}

export function CompetitorSignalList({ items, locale }: { items: CompetitorVideoSignal[]; locale: Locale }) {
  return (
    <Panel>
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
        {t(locale, "competitorMomentum")}
      </p>
      <p className="mt-2 text-sm leading-6 text-[var(--muted-foreground)]">
        {t(locale, "competitorHelp")}
      </p>
      <div className="mt-4 space-y-3">
        {items.map((item) => (
          <a
            key={item.id}
            href={item.url}
            target="_blank"
            rel="noreferrer"
            className="block rounded-2xl bg-[var(--background)] p-3 transition-colors hover:bg-white"
          >
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-[var(--foreground)]">{item.channelName}</p>
              <span className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">
                {getPerformanceBandLabel(locale, item.performanceBand)}
              </span>
            </div>
            <p className="mt-2 text-sm leading-6 text-[var(--foreground)]">{item.title}</p>
            <p className="mt-2 text-sm text-[var(--muted-foreground)]">{item.topicLabel}</p>
            <div className="mt-3 flex items-center justify-between text-xs text-[var(--muted-foreground)]">
              <span>{item.views.toLocaleString()} {t(locale, "views")}</span>
              <span>{item.viewsPerDay.toLocaleString()} {t(locale, "perDay")}</span>
              <span>{formatRelative(item.publishedAt, locale)}</span>
            </div>
            <p className="mt-2 text-sm leading-6 text-[var(--muted-foreground)]">{item.notes}</p>
          </a>
        ))}
      </div>
    </Panel>
  );
}

export function CommercialSnapshot({ candidates, locale }: { candidates: TopicCandidate[]; locale: Locale }) {
  const shootNow = candidates.filter((candidate) => candidate.decision === "shoot_now");
  const avgBreakEven = candidates.length
    ? Math.round(
        candidates.reduce((sum, candidate) => sum + candidate.economics.breakEvenViews, 0) /
          candidates.length,
      )
    : 0;
  const avgCost = candidates.length
    ? Math.round(
        candidates.reduce((sum, candidate) => sum + candidate.economics.totalCostUsd, 0) /
          candidates.length,
      )
    : 0;

  return (
    <Panel>
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
        {t(locale, "commercialSnapshot")}
      </p>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className="rounded-2xl bg-[var(--background)] p-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{t(locale, "shootNow")}</p>
          <p className="mt-1 text-2xl font-semibold text-[var(--foreground)]">{shootNow.length}</p>
        </div>
        <div className="rounded-2xl bg-[var(--background)] p-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{t(locale, "avgCost")}</p>
          <p className="mt-1 text-2xl font-semibold text-[var(--foreground)]">${avgCost}</p>
        </div>
        <div className="rounded-2xl bg-[var(--background)] p-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{t(locale, "avgBreakEven")}</p>
          <p className="mt-1 text-2xl font-semibold text-[var(--foreground)]">
            {avgBreakEven.toLocaleString()}
          </p>
        </div>
        <div className="rounded-2xl bg-[var(--background)] p-3">
          <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{t(locale, "topScore")}</p>
          <p className="mt-1 text-2xl font-semibold text-[var(--foreground)]">
            {candidates[0]?.youtubePotentialScore ?? 0}
          </p>
        </div>
      </div>
      <p className="mt-4 text-sm leading-6 text-[var(--muted-foreground)]">
        {t(locale, "commercialHelp")}
      </p>
    </Panel>
  );
}
