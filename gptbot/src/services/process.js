const { spawn } = require("child_process");

function runProcess(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd || process.cwd(),
      windowsHide: true,
      shell: false,
    });

    let stdout = "";
    let stderr = "";
    let settled = false;

    const timeoutMs = options.timeoutMs || 30000;
    const timer = setTimeout(() => {
      if (!settled) {
        settled = true;
        child.kill();
        reject(new Error(`Process timeout after ${timeoutMs} ms`));
      }
    }, timeoutMs);

    child.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    child.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    child.on("error", (error) => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        reject(error);
      }
    });

    child.on("close", (code) => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        resolve({
          code,
          stdout,
          stderr,
        });
      }
    });
  });
}

module.exports = {
  runProcess,
};
