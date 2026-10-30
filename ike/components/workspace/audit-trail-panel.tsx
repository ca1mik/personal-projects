import { Panel } from "@/components/ui/panel";
import type { AuditEvent, User } from "@/lib/domain/pipeline";
import { type Locale, t } from "@/lib/i18n";
import { formatDateTime } from "@/lib/utils";

function resolveActor(users: User[], actorUserId: string | null, locale: Locale) {
  if (!actorUserId) {
    return t(locale, "system");
  }

  return users.find((user) => user.id === actorUserId)?.name ?? t(locale, "unknownUser");
}

export function AuditTrailPanel({
  events,
  users,
  locale,
}: {
  events: AuditEvent[];
  users: User[];
  locale: Locale;
}) {
  return (
    <Panel>
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
        {t(locale, "auditTrail")}
      </p>
      <div className="mt-4 space-y-3">
        {events.length ? (
          events.slice(0, 8).map((event) => (
            <div key={event.id} className="rounded-2xl bg-[var(--background)] p-3">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-semibold text-[var(--foreground)]">{event.message}</p>
                <span className="text-[11px] uppercase tracking-[0.14em] text-[var(--muted-foreground)]">
                  {event.type.replaceAll("_", " ")}
                </span>
              </div>
              <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                {resolveActor(users, event.actorUserId, locale)} · {formatDateTime(event.createdAt, locale)}
              </p>
            </div>
          ))
        ) : (
          <p className="text-sm text-[var(--muted-foreground)]">{t(locale, "noAuditEvents")}</p>
        )}
      </div>
    </Panel>
  );
}
