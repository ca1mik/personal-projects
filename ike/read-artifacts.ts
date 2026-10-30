import { readFileSync } from "fs";

function loadEnv(p: string) {
  try {
    readFileSync(p, "utf8")
      .split("\n")
      .forEach((l) => {
        const eq = l.indexOf("=");
        if (eq < 1 || l.startsWith("#")) return;
        const k = l.slice(0, eq).trim();
        const v = l.slice(eq + 1).trim().replace(/^"|"$/g, "");
        if (!process.env[k]) process.env[k] = v;
      });
  } catch {}
}
loadEnv(".env.local");
loadEnv(".env");

const projectId = "project_XT68V9-xn-";
const raw = readFileSync("./storage/store.json", "utf8");
const store = JSON.parse(raw) as { artifacts: Array<Record<string, unknown>> };

const arts = store.artifacts
  .filter((a) => a.projectId === projectId)
  .sort((a, b) => (b.version as number) - (a.version as number));

const steps = [
  "editorial_angle",
  "script_outline",
  "draft_writer",
  "voice_edit",
  "final_qc",
];

for (const stepId of steps) {
  const a = arts.find((a) => a.stepName === stepId);
  if (!a) {
    console.log(`${stepId}: NOT FOUND\n`);
    continue;
  }
  const content = (a.contentJson as Record<string, unknown>)?.content;
  const summary = (a.contentJson as Record<string, unknown>)?.summary;
  console.log(`\n${"=".repeat(60)}`);
  console.log(`STEP: ${stepId} (v${a.version})`);
  console.log(`SUMMARY: ${summary}`);
  console.log(`CONTENT:\n${JSON.stringify(content, null, 2)}`);
  if (Array.isArray(a.qcNotes) && (a.qcNotes as string[]).length > 0) {
    console.log(`QC NOTES:\n${(a.qcNotes as string[]).map((n) => "  • " + n).join("\n")}`);
  }
}
