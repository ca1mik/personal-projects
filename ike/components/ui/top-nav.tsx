import Link from "next/link";
import type { Locale } from "@/lib/i18n";

export function TopNav({ locale, backHref, backLabel }: {
  locale?: Locale;
  backHref?: string;
  backLabel?: string;
}) {
  const isRu = locale === "ru";
  return (
    <nav className="sticky top-0 z-50 border-b border-[var(--border)] bg-[var(--panel)] backdrop-blur-md">
      <div className="mx-auto max-w-[1600px] flex items-center justify-between gap-4 px-4 py-3 md:px-6">
        {/* Brand */}
        <Link
          href="/"
          className="flex items-center gap-2 text-sm font-semibold text-[var(--foreground)] hover:text-[var(--accent)] transition-colors"
        >
          <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--accent)] text-white text-xs font-bold">
            Ike
          </span>
          <span className="hidden sm:inline">Editorial Pipeline</span>
        </Link>

        {/* Center nav links */}
        <div className="flex items-center gap-1">
          <Link
            href="/projects"
            className="inline-flex h-9 items-center gap-1.5 rounded-xl px-3 text-sm font-medium text-[var(--muted-foreground)] hover:bg-[var(--background)] hover:text-[var(--foreground)] transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 7h18M3 12h18M3 17h18" />
            </svg>
            {isRu ? "Все проекты" : "All Projects"}
          </Link>
          <Link
            href="/radar"
            className="inline-flex h-9 items-center gap-1.5 rounded-xl px-3 text-sm font-medium text-[var(--muted-foreground)] hover:bg-[var(--background)] hover:text-[var(--foreground)] transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1.5" fill="currentColor" />
            </svg>
            {isRu ? "Радар тем" : "Topic Radar"}
          </Link>
        </div>

        {/* Right: New project CTA */}
        <div className="flex items-center gap-2">
          {backHref && backLabel && (
            <Link
              href={backHref}
              className="hidden sm:inline-flex h-9 items-center gap-1.5 rounded-xl border border-[var(--border)] bg-[var(--background)] px-3 text-sm font-medium text-[var(--foreground)] hover:bg-white transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
              {backLabel}
            </Link>
          )}
          <Link
            href="/projects"
            className="inline-flex h-9 items-center gap-1.5 rounded-xl bg-[var(--accent)] px-3 text-sm font-semibold text-white hover:bg-[var(--accent-strong)] transition-colors shadow-sm"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            {isRu ? "Новый проект" : "New Project"}
          </Link>
        </div>
      </div>
    </nav>
  );
}
