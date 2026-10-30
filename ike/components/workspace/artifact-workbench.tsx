import Link from "next/link";
import {
  approveArtifactAction,
  generateStepAction,
  requestRevisionAction,
  saveArtifactDraftAction,
  sendToNextStepAction,
} from "@/app/actions";
import { Panel } from "@/components/ui/panel";
import { ProvenanceBadge } from "@/components/ui/provenance-badge";
import { StatusBadge } from "@/components/ui/status-badge";
import { SubmitButton } from "@/components/ui/submit-button";
import type { Artifact, StepId, StepRun, User } from "@/lib/domain/pipeline";
import {
  extractReadableContent,
  extractQcNotes,
  extractRequiredEdits,
  stripFirstHeading,
} from "@/lib/content-utils";
import { type Locale, getRoleLabel, t, withLang } from "@/lib/i18n";
import { formatDateTime } from "@/lib/utils";

export function ArtifactWorkbench({
  projectId,
  stepId,
  stepLabel,
  artifact,
  versions,
  requiresApproval,
  latestRun,
  currentUser,
  canApprove,
  isStale,
  blockingIssue,
  locale,
}: {
  projectId: string;
  stepId: StepId;
  stepLabel: string;
  artifact: Artifact | null;
  versions: Artifact[];
  requiresApproval: boolean;
  latestRun: StepRun | null;
  currentUser: User | null;
  canApprove: boolean;
  isStale: boolean;
  blockingIssue: string | null;
  locale: Locale;
}) {
  const artifactJson = artifact ? JSON.stringify(artifact.contentJson, null, 2) : "";
  const returnTo = withLang(`/projects/${projectId}?step=${stepId}`, locale);
  const displayStatus = artifact ? (isStale ? "blocked" : artifact.status) : null;

  // ── Parsed content ────────────────────────────────────────────────
  const readableContent = artifact
    ? stripFirstHeading(
        extractReadableContent(
          artifact.contentMarkdown,
          artifact.contentJson as Record<string, unknown>
        )
      )
    : "";

  const qcNotes = artifact
    ? extractQcNotes(
        artifact.qcNotes,
        artifact.contentJson as Record<string, unknown>
      )
    : [];

  const requiredEdits = artifact
    ? extractRequiredEdits(artifact.contentJson as Record<string, unknown>)
    : [];

  return (
    <div className="space-y-4">
      {/* ── Main content card ─────────────────────────── */}
      <Panel className="overflow-hidden p-0">
        {/* Header */}
        <div className="border-b border-[var(--border)] px-5 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
                {t(locale, "currentStep")}
              </p>
              <h2 className="mt-2 text-2xl font-semibold text-[var(--foreground)]">{stepLabel}</h2>
            </div>
            {artifact && (
              <div className="flex items-center gap-2">
                <ProvenanceBadge provenance={artifact.provenance} locale={locale} />
                {displayStatus && <StatusBadge status={displayStatus} locale={locale} />}
              </div>
            )}
          </div>
        </div>

        {artifact ? (
          <div className="px-5 py-5 space-y-4">
            {/* ── Blocking / warning notice ── */}
            {(blockingIssue ||
              (artifact.provenance.note &&
                artifact.provenance.mode !== "live_model")) && (
              <div className="rounded-2xl border border-[#f2d6ce] bg-[#fff8f7] px-4 py-3 text-sm leading-6 text-[#7b3a31]">
                ⚠ {blockingIssue ?? artifact.provenance.note}
              </div>
            )}

            {/* ── QC issues (замечания по качеству) ── */}
            {qcNotes.length > 0 && (
              <div className="rounded-2xl border border-[#eee1c3] bg-[#fffbf2] px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#72551d] mb-2">
                  {locale === "ru" ? "Замечания по качеству" : "Quality Notes"}
                </p>
                <ul className="space-y-1.5">
                  {qcNotes.map((note, i) => (
                    <li key={i} className="flex gap-2 text-sm leading-6 text-[#6e5325]">
                      <span className="mt-0.5 shrink-0 text-amber-600">•</span>
                      <span>{note}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* ── Required edits (if any, e.g. final_qc) ── */}
            {requiredEdits.length > 0 && (
              <div className="rounded-2xl border border-[#d6e2f0] bg-[#f4f8fc] px-4 py-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#1d4e6a] mb-2">
                  {locale === "ru" ? "Необходимые правки" : "Required Edits"}
                </p>
                <ol className="space-y-1.5 list-none">
                  {requiredEdits.map((edit, i) => (
                    <li key={i} className="flex gap-2 text-sm leading-6 text-[#264f67]">
                      <span className="shrink-0 font-semibold text-[#1d4e6a]">{i + 1}.</span>
                      <span>{edit}</span>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {/* ── Main readable content ── */}
            <div className="rounded-[22px] bg-[var(--background)] px-5 py-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)] mb-4">
                {locale === "ru" ? "Содержание" : "Content"}
              </p>
              <div className="text-sm leading-7 text-[var(--foreground)] whitespace-pre-wrap font-sans">
                {readableContent || (
                  <span className="text-[var(--muted-foreground)] italic">
                    {locale === "ru" ? "Контент пуст." : "No content yet."}
                  </span>
                )}
              </div>
            </div>

            {/* ── Edit form (collapsible) ── */}
            <details className="rounded-[22px] border border-[var(--border)] overflow-hidden group">
              <summary className="cursor-pointer px-5 py-3 text-sm font-medium text-[var(--muted-foreground)] hover:bg-[var(--background)] flex items-center gap-2 select-none list-none">
                <svg
                  className="w-4 h-4 transition-transform group-open:rotate-90"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
                {locale === "ru" ? "Редактировать вручную" : "Edit manually"}
              </summary>
              <form
                action={saveArtifactDraftAction}
                className="space-y-4 px-5 py-5 bg-[var(--background)]"
              >
                <input type="hidden" name="projectId" value={projectId} />
                <input type="hidden" name="stepId" value={stepId} />
                <input type="hidden" name="returnTo" value={returnTo} />
                <input type="hidden" name="parentArtifactId" value={artifact.id} />
                <input type="hidden" name="contentJson" value={artifactJson} />
                <label className="grid gap-1.5 text-sm text-[var(--muted-foreground)]">
                  {t(locale, "artifactTitle")}
                  <input
                    name="title"
                    defaultValue={artifact.title}
                    className="h-10 rounded-xl border border-[var(--border)] bg-white/50 px-3 text-[var(--foreground)]"
                  />
                </label>
                <label className="grid gap-1.5 text-sm text-[var(--muted-foreground)]">
                  {locale === "ru" ? "Текст" : "Text"}
                  <textarea
                    name="contentMarkdown"
                    defaultValue={artifact.contentMarkdown}
                    rows={14}
                    className="rounded-2xl border border-[var(--border)] bg-white/50 px-3 py-3 text-sm leading-6 text-[var(--foreground)]"
                  />
                </label>
                <label className="grid gap-1.5 text-sm text-[var(--muted-foreground)]">
                  {locale === "ru" ? "Комментарий к правке" : "Revision note"}
                  <textarea
                    name="qcNotes"
                    defaultValue={artifact.qcNotes.join("\n")}
                    rows={3}
                    placeholder={locale === "ru" ? "Что нужно исправить..." : "What needs fixing..."}
                    className="rounded-2xl border border-[var(--border)] bg-white/50 px-3 py-3 text-sm leading-6 text-[var(--foreground)]"
                  />
                </label>
                <SubmitButton
                  label={t(locale, "saveDraft")}
                  pendingLabel={t(locale, "saving")}
                />
              </form>
            </details>

            {/* ── Meta strip ── */}
            {latestRun && (
              <div className="flex flex-wrap gap-4 px-1 text-xs text-[var(--muted-foreground)]">
                <span>
                  {t(locale, "model")}: {artifact.provenance.modelName ?? "n/a"}
                </span>
                <span>{t(locale, "tokens")}: {latestRun.tokenEstimate ?? 0}</span>
                <span>
                  {t(locale, "costEstimate")}: ${latestRun.costEstimateUsd?.toFixed(4) ?? "0.0000"}
                </span>
              </div>
            )}
          </div>
        ) : (
          /* ── Empty state ── */
          <div className="px-5 py-10">
            <div className="rounded-[22px] bg-[var(--background)] p-6 text-center">
              <p className="text-base font-medium text-[var(--foreground)]">
                {t(locale, "noArtifactYet")}
              </p>
              <p className="mt-2 max-w-xl mx-auto text-sm leading-6 text-[var(--muted-foreground)]">
                {t(locale, "generationHelp")}
              </p>
              <form action={generateStepAction} className="mt-5">
                <input type="hidden" name="projectId" value={projectId} />
                <input type="hidden" name="stepId" value={stepId} />
                <input type="hidden" name="returnTo" value={returnTo} />
                <SubmitButton
                  label={t(locale, "generate")}
                  pendingLabel={t(locale, "generating")}
                />
              </form>
            </div>
          </div>
        )}
      </Panel>

      {/* ── Action bar ────────────────────────────────── */}
      <Panel>
        <div className="flex flex-wrap items-start gap-3">
          {artifact ? (
            <>
              {/* Regenerate */}
              <form action={generateStepAction}>
                <input type="hidden" name="projectId" value={projectId} />
                <input type="hidden" name="stepId" value={stepId} />
                <input type="hidden" name="returnTo" value={returnTo} />
                <SubmitButton
                  label={t(locale, "regenerate")}
                  pendingLabel={t(locale, "generating")}
                  variant="secondary"
                />
              </form>

              {/* Approve */}
              {requiresApproval &&
                (isStale ? (
                  <div className="rounded-2xl bg-[var(--background)] px-4 py-2.5 text-sm text-[#7b3a31]">
                    {locale === "ru"
                      ? "Обновите артефакт перед утверждением."
                      : "Refresh artifact before approving again."}
                  </div>
                ) : canApprove ? (
                  <form action={approveArtifactAction}>
                    <input type="hidden" name="projectId" value={projectId} />
                    <input type="hidden" name="artifactId" value={artifact.id} />
                    <input type="hidden" name="returnTo" value={returnTo} />
                    <SubmitButton
                      label={t(locale, "approve")}
                      pendingLabel={t(locale, "approving")}
                    />
                  </form>
                ) : (
                  <div className="rounded-2xl bg-[var(--background)] px-4 py-2.5 text-sm text-[#7b3a31]">
                    {currentUser
                      ? getRoleLabel(locale, currentUser.role)
                      : locale === "ru"
                      ? "Текущая роль"
                      : "Current role"}{" "}
                    {t(locale, "cannotApprove")}
                  </div>
                ))}

              {/* Send to next step */}
              <form action={sendToNextStepAction}>
                <input type="hidden" name="projectId" value={projectId} />
                <input type="hidden" name="stepId" value={stepId} />
                <input type="hidden" name="returnTo" value={returnTo} />
                <SubmitButton
                  label={
                    isStale
                      ? t(locale, "resolveUpstreamChanges")
                      : t(locale, "sendToNextStep")
                  }
                  pendingLabel={t(locale, "sending")}
                  variant="secondary"
                />
              </form>

              {/* Request revision */}
              <form
                action={requestRevisionAction}
                className="flex-1 min-w-[240px] space-y-2"
              >
                <input type="hidden" name="projectId" value={projectId} />
                <input type="hidden" name="artifactId" value={artifact.id} />
                <input type="hidden" name="returnTo" value={returnTo} />
                <textarea
                  name="revisionNotes"
                  rows={2}
                  placeholder={t(locale, "revisionPlaceholder")}
                  className="w-full rounded-2xl border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm text-[var(--foreground)]"
                />
                <SubmitButton
                  label={t(locale, "requestRevision")}
                  pendingLabel={t(locale, "updating")}
                  variant="danger"
                />
              </form>
            </>
          ) : (
            <form action={generateStepAction}>
              <input type="hidden" name="projectId" value={projectId} />
              <input type="hidden" name="stepId" value={stepId} />
              <input type="hidden" name="returnTo" value={returnTo} />
              <SubmitButton
                label={t(locale, "generate")}
                pendingLabel={t(locale, "generating")}
              />
            </form>
          )}
        </div>
      </Panel>

      {/* ── Version history ─────────────────────────── */}
      {versions.length > 0 && (
        <Panel>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
            {t(locale, "versionHistory")}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {versions.map((version) => (
              <Link
                key={version.id}
                href={withLang(
                  `/projects/${projectId}/artifacts/${stepId}?version=${version.version}`,
                  locale
                )}
                className="inline-flex items-center gap-2 rounded-xl bg-[var(--background)] px-3 py-2 text-sm transition-colors hover:bg-white"
              >
                <span className="font-semibold text-[var(--foreground)]">
                  v{version.version}
                </span>
                <StatusBadge status={version.status} locale={locale} />
                <span className="text-xs text-[var(--muted-foreground)]">
                  {formatDateTime(version.updatedAt, locale)}
                </span>
              </Link>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}
