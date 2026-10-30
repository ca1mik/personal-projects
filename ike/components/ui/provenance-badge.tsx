import type { Artifact } from "@/lib/domain/pipeline";
import { type Locale, getProvenanceLabel } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const provenanceTone: Record<Artifact["provenance"]["mode"], string> = {
  live_model: "bg-[#dbe5ea] text-[#345267]",
  demo_fallback: "bg-[#f2d6ce] text-[#7b3a31]",
  human_edit: "bg-[#d8e6d4] text-[#2e5a3c]",
};

export function ProvenanceBadge({
  provenance,
  className,
  locale = "en",
}: {
  provenance: Artifact["provenance"];
  className?: string;
  locale?: Locale;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em]",
        provenanceTone[provenance.mode],
        className,
      )}
    >
      {getProvenanceLabel(locale, provenance.mode)}
    </span>
  );
}
