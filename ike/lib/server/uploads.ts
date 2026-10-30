import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { slugifyFileName } from "@/lib/utils";

export async function persistUpload(projectId: string, file: File) {
  const bytes = await file.arrayBuffer();
  const buffer = Buffer.from(bytes);
  const fileName = `${Date.now()}-${slugifyFileName(file.name)}`;
  const dir = path.join(process.cwd(), "storage", "uploads", projectId);
  const absolutePath = path.join(dir, fileName);
  const relativePath = path.join("storage", "uploads", projectId, fileName);

  await mkdir(dir, { recursive: true });
  await writeFile(absolutePath, buffer);

  let extractedText = "";
  const isTextLike =
    file.type.startsWith("text/") ||
    file.type.includes("json") ||
    file.type.includes("csv") ||
    file.name.endsWith(".md");

  if (isTextLike) {
    extractedText = await file.text();
  } else {
    extractedText = `Uploaded binary file "${file.name}" (${file.type || "unknown type"}). Extracted text is not available in MVP mode.`;
  }

  return {
    relativePath,
    extractedText,
  };
}
