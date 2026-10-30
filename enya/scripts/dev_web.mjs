import { spawn } from "node:child_process";

const child = spawn("pnpm", ["--dir", "apps/web", "dev"], {
  cwd: process.cwd(),
  stdio: "inherit",
  shell: process.platform === "win32",
  env: process.env
});

child.on("exit", (code) => {
  process.exit(code ?? 0);
});

