import Link from "next/link";
import { refreshTopicRadarAction } from "@/app/actions";
import { TopicCandidateCard } from "@/components/radar/topic-candidate-card";
import { CommercialSnapshot, CompetitorSignalList, NewsSignalList, SourceList } from "@/components/radar/signal-list";
import { FlashNotice } from "@/components/ui/flash-notice";
import { LocaleToggle } from "@/components/ui/locale-toggle";
import { Panel } from "@/components/ui/panel";
import { SessionSwitcher } from "@/components/ui/session-switcher";
import { SubmitButton } from "@/components/ui/submit-button";
import { getCurrentUser, getTopicRadarSnapshot, listUsers } from "@/lib/data/repository";
import { getLocaleFromCookies, resolveLocale, t, withLang } from "@/lib/i18n";

export const dynamic = "force-dynamic";

export default async function RadarPage(props: {
  searchParams: Promise<{ notice?: string; error?: string; lang?: string }>;
}) {
  const searchParams = await props.searchParams;
  const locale = resolveLocale(searchParams.lang, await getLocaleFromCookies());
  const [radar, users, currentUser] = await Promise.all([getTopicRadarSnapshot(), listUsers(), getCurrentUser()]);
  const hotCount = radar.candidates.filter((candidate) => candidate.status === "hot").length;

  return (
    <main className="workspace-shell min-h-screen px-4 py-6 md:px-6 lg:px-8">
      <div className="mx-auto max-w-[1600px] space-y-6">
        <header className="rounded-[28px] border border-[var(--border)] bg-[var(--panel)] px-6 py-6 shadow-[0_20px_60px_rgba(35,33,28,0.06)]">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <Link
                href={withLang("/projects", locale)}
                className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]"
              >
                {t(locale, "backToProjects")}
              </Link>
              <h1 className="mt-3 font-serif text-4xl font-semibold tracking-tight text-[var(--foreground)]">
                {t(locale, "topicRadar")}
              </h1>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--muted-foreground)]">
                {t(locale, "topicRadarSubtitle")}
              </p>
            </div>
            <Panel className="grid min-w-[320px] grid-cols-3 gap-3 p-4">
              <div>
                <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{t(locale, "sources")}</p>
                <p className="mt-1 text-2xl font-semibold text-[var(--foreground)]">{radar.sources.length}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{t(locale, "signals")}</p>
                <p className="mt-1 text-2xl font-semibold text-[var(--foreground)]">{radar.signals.length}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">{t(locale, "hotTopics")}</p>
                <p className="mt-1 text-2xl font-semibold text-[var(--foreground)]">{hotCount}</p>
              </div>
            </Panel>
          </div>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <form action={refreshTopicRadarAction}>
              <input type="hidden" name="returnTo" value={withLang("/radar", locale)} />
              <SubmitButton label={t(locale, "refreshRadar")} pendingLabel={t(locale, "refreshing")} />
            </form>
            <LocaleToggle locale={locale} returnTo="/radar" />
          </div>
          <div className="mt-5">
            <SessionSwitcher currentUser={currentUser} users={users} returnTo={withLang("/radar", locale)} locale={locale} />
          </div>
        </header>

        <FlashNotice notice={searchParams.notice} error={searchParams.error} />

        <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="space-y-4">
            <div className="grid gap-4 2xl:grid-cols-2">
              {radar.candidates.map((candidate) => (
                <TopicCandidateCard key={candidate.id} candidate={candidate} locale={locale} />
              ))}
            </div>
            <NewsSignalList signals={radar.signals} locale={locale} />
          </div>
          <div className="space-y-4">
            <CommercialSnapshot candidates={radar.candidates} locale={locale} />
            <SourceList sources={radar.sources} locale={locale} />
            <CompetitorSignalList items={radar.competitorSignals} locale={locale} />
          </div>
        </section>
      </div>
    </main>
  );
}
