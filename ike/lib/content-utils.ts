/**
 * Extracts the human-readable portion from contentMarkdown.
 *
 * Strips: code fences, ## Structured Content, ## QC Notes, # headings like `# step_name`
 */
export function extractReadableContent(
  contentMarkdown: string,
  contentJson: Record<string, unknown> | null | undefined
): string {
  // 1. If there's a final_script in JSON, use that (final_qc step)
  if (contentJson && typeof contentJson.final_script === "string") {
    return contentJson.final_script.trim();
  }

  // 2. Remove lines that are `# word` (step ids like `# channel_diagnosis`)
  let md = contentMarkdown.replace(/^#\s+\S+\s*$/m, "").trim();

  // 3. Cut at any H2 section that starts with "Structured" or has a code fence
  const cutPatterns = [
    /^##\s+(Structured|QC Notes|Citations)/im,
    /^```/m,
  ];
  for (const pattern of cutPatterns) {
    const idx = md.search(pattern);
    if (idx !== -1) {
      const before = md.slice(0, idx).trim();
      if (before.length > 20) {
        md = before;
        break;
      }
    }
  }

  // 4. Remove any remaining ``` blocks
  md = md.replace(/```[\s\S]*?```/g, "").trim();

  // 5. Remove any remaining ## headings that start with "Structured"
  md = md.replace(/^##\s+Structured.*$/gim, "").trim();

  return md;
}

/**
 * Strips the first `# heading` line from a markdown string (usually the step id slug).
 */
export function stripFirstHeading(text: string): string {
  return text.replace(/^#\s+\S[\s\S]*?\n/, "").trim();
}

/**
 * Extracts QC notes from the artifact's qcNotes array or from contentJson.qc_notes.
 */
export function extractQcNotes(
  qcNotes: string[],
  contentJson: Record<string, unknown> | null | undefined
): string[] {
  if (qcNotes.length > 0) return qcNotes;
  if (contentJson && Array.isArray(contentJson.qc_notes)) {
    return (contentJson.qc_notes as string[]).filter(Boolean);
  }
  return [];
}

/**
 * Extracts required_edits from contentJson (used in final_qc step).
 */
export function extractRequiredEdits(
  contentJson: Record<string, unknown> | null | undefined
): string[] {
  if (!contentJson || !Array.isArray(contentJson.required_edits)) return [];
  return (contentJson.required_edits as string[]).filter(Boolean);
}
