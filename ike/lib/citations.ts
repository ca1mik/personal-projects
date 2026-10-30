import type { Artifact, Source } from "@/lib/domain/pipeline";

export type CitationClaim = {
  claim: string;
  sourceRefs: string[];
  note: string | null;
};

export type CitationCheck = CitationClaim & {
  status: "verified" | "needs_review" | "missing_support";
};

function asStringArray(value: unknown) {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

export function createSourceRef(value: string) {
  const normalized = value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .replace(/_+/g, "_")
    .slice(0, 48);

  return `src_${normalized || "source"}`;
}

export function normalizeSourceRef(value: string | null | undefined, fallbackTitle: string) {
  const raw = typeof value === "string" ? value.trim() : "";
  return raw ? createSourceRef(raw) : createSourceRef(fallbackTitle);
}

export function extractArtifactCitations(artifact: Artifact | null): CitationClaim[] {
  if (!artifact || !artifact.contentJson || typeof artifact.contentJson !== "object") {
    return [];
  }

  const content = artifact.contentJson.content as Record<string, unknown> | undefined;
  if (!content || typeof content !== "object") {
    return [];
  }

  if (artifact.stepName === "draft_writer") {
    const claims = Array.isArray(content.cited_claims) ? content.cited_claims : [];
    return claims
      .map((item) => {
        if (!item || typeof item !== "object") {
          return null;
        }

        const claim = typeof item.claim === "string" ? item.claim.trim() : "";
        if (!claim) {
          return null;
        }

        return {
          claim,
          sourceRefs: asStringArray(item.source_refs),
          note: typeof item.note === "string" && item.note.trim().length ? item.note : null,
        } satisfies CitationClaim;
      })
      .filter((item): item is CitationClaim => item !== null);
  }

  if (artifact.stepName === "final_qc") {
    const checks = Array.isArray(content.citation_checks) ? content.citation_checks : [];
    return checks
      .map((item) => {
        if (!item || typeof item !== "object") {
          return null;
        }

        const claim = typeof item.claim === "string" ? item.claim.trim() : "";
        if (!claim) {
          return null;
        }

        return {
          claim,
          sourceRefs: asStringArray(item.source_refs),
          note: typeof item.note === "string" && item.note.trim().length ? item.note : null,
        } satisfies CitationClaim;
      })
      .filter((item): item is CitationClaim => item !== null);
  }

  return [];
}

export function extractArtifactCitationChecks(artifact: Artifact | null): CitationCheck[] {
  if (!artifact || artifact.stepName !== "final_qc") {
    return [];
  }

  const content = artifact.contentJson.content as Record<string, unknown> | undefined;
  if (!content || typeof content !== "object") {
    return [];
  }

  const checks = Array.isArray(content.citation_checks) ? content.citation_checks : [];
  return checks
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }

      const claim = typeof item.claim === "string" ? item.claim.trim() : "";
      if (!claim) {
        return null;
      }

      const status =
        item.status === "verified" || item.status === "needs_review" || item.status === "missing_support"
          ? item.status
          : "needs_review";

      return {
        claim,
        sourceRefs: asStringArray(item.source_refs),
        note: typeof item.note === "string" && item.note.trim().length ? item.note : null,
        status,
      } satisfies CitationCheck;
    })
    .filter((item): item is CitationCheck => item !== null);
}

export function getAllSourceRefs(sources: Source[]) {
  return new Set(
    sources
      .map((source) => source.sourceRef)
      .filter((sourceRef): sourceRef is string => typeof sourceRef === "string" && sourceRef.trim().length > 0),
  );
}
