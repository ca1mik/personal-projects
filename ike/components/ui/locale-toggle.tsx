import Link from "next/link";
import { type Locale, t, withLang } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function LocaleToggle({
  locale,
  returnTo,
}: {
  locale: Locale;
  returnTo: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
        {t(locale, "language")}
      </span>
      <div className="inline-flex rounded-full border border-[var(--border)] bg-[var(--background)] p-1">
        {(["ru", "en"] as const).map((option) => (
          <Link
            key={option}
            href={withLang(returnTo, option)}
            className={cn(
              "inline-flex h-8 min-w-[48px] items-center justify-center rounded-full px-3 text-xs font-semibold uppercase tracking-[0.14em] transition-colors",
              locale === option
                ? "bg-[var(--foreground)] text-[var(--background)]"
                : "text-[var(--muted-foreground)] hover:bg-white",
            )}
          >
            {option}
          </Link>
        ))}
      </div>
    </div>
  );
}
