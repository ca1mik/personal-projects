import { uploadMaterialAction } from "@/app/actions";
import { Panel } from "@/components/ui/panel";
import { SubmitButton } from "@/components/ui/submit-button";
import type { ProjectWorkspace } from "@/lib/data/repository";
import type { Artifact, Source, Upload } from "@/lib/domain/pipeline";
import { type Locale, getUploadKindLabel, t, withLang } from "@/lib/i18n";
import { formatDateTime } from "@/lib/utils";

// Simple check/cross icon helper
function Check({ ok }: { ok: boolean }) {
  return (
    <span className={ok ? "text-emerald-600 font-bold" : "text-red-400"}>
      {ok ? "✓" : "✗"}
    </span>
  );
}

export function ContextSidebar({
  projectId,
  inputArtifacts,
  uploads,
  sources,
  qcNotes,
  controls,
  locale,
}: {
  projectId: string;
  inputArtifacts: Artifact[];
  uploads: Upload[];
  sources: Source[];
  qcNotes: string[];
  controls: ProjectWorkspace["controls"];
  locale: Locale;
}) {
  return (
    <div className="space-y-4">
      {/* ── Project health (compact) ─────────────────── */}
      <Panel className="p-0 overflow-hidden">
        <div className="border-b border-[var(--border)] px-4 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
            {locale === "ru" ? "Состояние проекта" : "Project Health"}
          </p>
        </div>

        {/* 3 key numbers */}
        <div className="grid grid-cols-3 border-b border-[var(--border)]">
          {[
            {
              label: locale === "ru" ? "Утверждено" : "Approved",
              value: `${controls.approvedCriticalSteps}/${controls.totalCriticalSteps}`,
            },
            {
              label: locale === "ru" ? "Источники" : "Sources",
              value: controls.sourceCoverageCount,
            },
            {
              label: locale === "ru" ? "Правки" : "Edits",
              value: controls.humanEditedArtifacts,
            },
          ].map((item) => (
            <div key={item.label} className="px-3 py-3 text-center">
              <p className="text-xl font-bold text-[var(--foreground)]">{item.value}</p>
              <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] mt-0.5">
                {item.label}
              </p>
            </div>
          ))}
        </div>

        {/* Checklist */}
        <div className="px-4 py-3 space-y-1.5">
          <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] mb-2">
            {locale === "ru" ? "Контрольный список" : "Checklist"}
          </p>
          {[
            { label: t(locale, "brief"), ok: controls.briefPresent },
            { label: t(locale, "transcript"), ok: controls.transcriptPresent },
            { label: t(locale, "metrics"), ok: controls.metricsPresent },
            { label: t(locale, "finalQcApproved"), ok: controls.finalQcApproved },
          ].map((item) => (
            <div key={item.label} className="flex items-center justify-between text-sm">
              <span className="text-[var(--foreground)]">{item.label}</span>
              <Check ok={item.ok} />
            </div>
          ))}
          {controls.staleArtifactCount > 0 && (
            <p className="text-xs text-amber-700 mt-1">
              ⚠ {controls.staleArtifactCount} {locale === "ru" ? "устаревших артефактов" : "stale artifacts"}
            </p>
          )}
        </div>

        {/* Gaps */}
        {controls.controlGaps.length > 0 && (
          <div className="border-t border-[var(--border)] px-4 py-3 space-y-1.5">
            <p className="text-[10px] uppercase tracking-[0.14em] text-red-500 mb-1.5">
              {locale === "ru" ? "Пробелы" : "Gaps"}
            </p>
            {controls.controlGaps.map((gap) => (
              <p key={gap} className="text-xs leading-5 text-[#7b3a31]">
                • {gap}
              </p>
            ))}
          </div>
        )}
      </Panel>

      {/* ── Input artifacts (previous steps) ─────────── */}
      {inputArtifacts.length > 0 && (
        <Panel className="p-0 overflow-hidden">
          <div className="border-b border-[var(--border)] px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
              {locale === "ru" ? "Входные данные" : "Input Data"}
            </p>
          </div>
          <div className="divide-y divide-[var(--border)]">
            {inputArtifacts.map((artifact) => (
              <div key={artifact.id} className="px-4 py-3">
                <p className="text-xs font-semibold text-[var(--foreground)] truncate">{artifact.title}</p>
                {artifact.contentJson?.summary && (
                  <p className="mt-1 text-xs leading-5 text-[var(--muted-foreground)] line-clamp-2">
                    {artifact.contentJson.summary}
                  </p>
                )}
              </div>
            ))}
          </div>
        </Panel>
      )}

      {/* ── Sources ──────────────────────────────────── */}
      {sources.length > 0 && (
        <Panel className="p-0 overflow-hidden">
          <div className="border-b border-[var(--border)] px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
              {t(locale, "sources")}
            </p>
          </div>
          <div className="divide-y divide-[var(--border)]">
            {sources.map((source) => (
              <div key={source.id} className="px-4 py-3">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-xs font-semibold text-[var(--foreground)] leading-5 flex-1">{source.title}</p>
                  <span className="font-mono text-[10px] text-[var(--muted-foreground)] shrink-0">{source.sourceRef}</span>
                </div>
                <p className="mt-1 text-xs leading-5 text-[var(--muted-foreground)] line-clamp-2">{source.summary}</p>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {/* ── File uploads ─────────────────────────────── */}
      <Panel className="p-0 overflow-hidden">
        <div className="border-b border-[var(--border)] px-4 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
            {t(locale, "uploads")}
          </p>
        </div>

        {uploads.length > 0 && (
          <div className="divide-y divide-[var(--border)]">
            {uploads.map((upload) => (
              <div key={upload.id} className="flex items-center justify-between gap-2 px-4 py-2.5">
                <p className="text-xs text-[var(--foreground)] truncate flex-1">{upload.fileName}</p>
                <span className="text-[10px] uppercase tracking-[0.14em] text-[var(--muted-foreground)] shrink-0">
                  {getUploadKindLabel(locale, upload.kind)}
                </span>
              </div>
            ))}
          </div>
        )}

        <form action={uploadMaterialAction} className="px-4 py-3 space-y-2">
          <input type="hidden" name="projectId" value={projectId} />
          <input type="hidden" name="returnTo" value={withLang(`/projects/${projectId}`, locale)} />
          <select
            name="kind"
            className="h-9 w-full rounded-xl border border-[var(--border)] bg-[var(--background)] px-3 text-sm text-[var(--foreground)]"
            defaultValue="material"
          >
            <option value="brief">{t(locale, "brief")}</option>
            <option value="transcript">{t(locale, "transcript")}</option>
            <option value="metrics">{t(locale, "metrics")}</option>
            <option value="notes">{t(locale, "notes")}</option>
            <option value="material">{t(locale, "material")}</option>
          </select>
          <input
            name="file"
            type="file"
            className="block w-full rounded-xl border border-dashed border-[var(--border)] bg-[var(--background)] px-3 py-2 text-xs text-[var(--muted-foreground)]"
          />
          <SubmitButton
            label={t(locale, "uploadMaterial")}
            pendingLabel={t(locale, "uploading")}
            variant="secondary"
          />
        </form>
      </Panel>
    </div>
  );
}
