import type { Change } from "diff";

export function DiffView({ changes }: { changes: Change[] }) {
  return (
    <div className="overflow-hidden rounded-[22px] border border-[var(--border)] bg-[var(--panel)]">
      <div className="border-b border-[var(--border)] px-4 py-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
          Version Diff
        </p>
      </div>
      <div className="divide-y divide-[var(--border)]">
        {changes.map((change, index) => {
          const tone = change.added
            ? "bg-[#e6f0e8] text-[#294735]"
            : change.removed
              ? "bg-[#f4e3dc] text-[#6c3931]"
              : "bg-[var(--background)] text-[var(--foreground)]";

          return (
            <pre
              key={`${index}-${change.count}`}
              className={`overflow-x-auto whitespace-pre-wrap px-4 py-3 text-sm leading-6 ${tone}`}
            >
              {change.value}
            </pre>
          );
        })}
      </div>
    </div>
  );
}
