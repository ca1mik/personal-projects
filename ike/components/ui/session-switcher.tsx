import { switchCurrentUserAction } from "@/app/actions";
import { SubmitButton } from "@/components/ui/submit-button";
import type { User } from "@/lib/domain/pipeline";
import { type Locale, getRoleLabel, t } from "@/lib/i18n";

export function SessionSwitcher({
  currentUser,
  users,
  returnTo,
  locale,
}: {
  currentUser: User | null;
  users: User[];
  returnTo: string;
  locale: Locale;
}) {
  return (
    <form action={switchCurrentUserAction} className="flex flex-wrap items-center gap-3">
      <input type="hidden" name="returnTo" value={returnTo} />
      <label className="grid gap-2 text-sm text-[var(--muted-foreground)]">
        {t(locale, "actingUser")}
        <select
          name="userId"
          defaultValue={currentUser?.id ?? users[0]?.id}
          className="h-10 min-w-[210px] rounded-xl border border-[var(--border)] bg-[var(--background)] px-3 text-sm text-[var(--foreground)]"
        >
          {users.map((user) => (
            <option key={user.id} value={user.id}>
              {user.name} ({getRoleLabel(locale, user.role)})
            </option>
          ))}
        </select>
      </label>
      <div className="pt-6">
        <SubmitButton
          label={t(locale, "switchSession")}
          pendingLabel={t(locale, "switching")}
          variant="secondary"
        />
      </div>
    </form>
  );
}
