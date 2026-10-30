const path = require("path");
const config = require("../config");
const { safeJsonParse } = require("../utils");
const { runProcess } = require("./process");

const scriptPath = path.join(process.cwd(), "scripts", "windows-tools.ps1");

async function runWindowsAction(action, args = {}, options = {}) {
  const powershellArgs = [
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    scriptPath,
    "-Action",
    action,
  ];

  Object.entries(args).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }

    powershellArgs.push(`-${key}`);
    powershellArgs.push(String(value));
  });

  const result = await runProcess("powershell", powershellArgs, {
    timeoutMs: options.timeoutMs || config.requestTimeoutMs,
  });

  const payload = safeJsonParse(result.stdout.trim(), null);
  if (!payload) {
    throw new Error(result.stderr.trim() || "Windows action returned invalid output");
  }

  if (!payload.success) {
    throw new Error(payload.message || "Windows action failed");
  }

  return payload;
}

module.exports = {
  runWindowsAction,
};
