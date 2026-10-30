require("dotenv").config();

const fs = require("fs");
const path = require("path");
const assert = require("assert");
const config = require("../src/config");
const { handleAssistantInput } = require("../src/assistant");
const { listModels, chat, transcribeAudio } = require("../src/services/ai");
const { runWindowsAction } = require("../src/services/windows");
const { runProcess } = require("../src/services/process");

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const tmpDir = path.join(process.cwd(), "tmp");

function log(message) {
  process.stdout.write(`${message}\n`);
}

async function check(name, fn) {
  log(`\n[TEST] ${name}`);
  try {
    await fn();
    log(`[PASS] ${name}`);
    return { name, ok: true };
  } catch (error) {
    log(`[FAIL] ${name}`);
    log(error.stack || error.message || String(error));
    return { name, ok: false, error };
  }
}

async function queryCursor() {
  const result = await runProcess(
    "powershell",
    [
      "-NoProfile",
      "-Command",
      "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Cursor]::Position | ConvertTo-Json -Compress",
    ],
    { timeoutMs: 10000 }
  );

  return JSON.parse(result.stdout.trim());
}

async function startTestPad(title, outputPath) {
  await runProcess(
    "powershell",
    [
      "-NoProfile",
      "-Command",
      `Start-Process powershell -ArgumentList '-STA','-NoProfile','-ExecutionPolicy','Bypass','-File','${path.join(
        process.cwd(),
        "scripts",
        "test-pad.ps1"
      )}','-Title','${title}','-OutputPath','${outputPath}','-LifetimeSeconds','45'`,
    ],
    { timeoutMs: 10000 }
  );

  await sleep(1800);
}

async function generateVoiceTestMp3(mp3Path) {
  const wavPath = mp3Path.replace(/\.mp3$/i, ".wav");

  await runProcess(
    "powershell",
    [
      "-NoProfile",
      "-Command",
      `Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.SetOutputToWaveFile('${wavPath}'); $s.Speak('Привет это тест голосового сообщения'); $s.Dispose()`,
    ],
    { timeoutMs: 30000 }
  );

  await runProcess(
    "ffmpeg",
    ["-y", "-i", wavPath, "-ac", "1", "-ar", "16000", "-codec:a", "libmp3lame", mp3Path],
    { timeoutMs: 60000 }
  );

  if (fs.existsSync(wavPath)) {
    fs.unlinkSync(wavPath);
  }
}

async function main() {
  fs.mkdirSync(tmpDir, { recursive: true });

  const results = [];

  results.push(
    await check("Syntax checks", async () => {
      const files = [
        "src/index.js",
        "src/assistant.js",
        "src/config.js",
        "src/state.js",
        "src/utils.js",
        "src/services/ai.js",
        "src/services/drafts.js",
        "src/services/file-search.js",
        "src/services/process.js",
        "src/services/voice.js",
        "src/services/windows.js",
      ];

      for (const file of files) {
        const result = await runProcess("node", ["--check", file], { timeoutMs: 10000 });
        assert.strictEqual(result.code, 0, `Syntax check failed for ${file}`);
      }
    })
  );

  results.push(
    await check("codex.sale chat", async () => {
      const answer = await chat("codexsale", config.codexSale.model, [
        { role: "system", content: "Reply with one word only." },
        { role: "user", content: "ok?" },
      ]);
      assert.ok(/ok/i.test(answer), `Unexpected codex.sale answer: ${answer}`);
    })
  );

  let ollamaModels = [];
  results.push(
    await check("Ollama list", async () => {
      ollamaModels = await listModels("ollama");
      assert.ok(ollamaModels.length > 0, "No Ollama models found");
      assert.ok(ollamaModels.includes(config.ollama.model), `Configured Ollama model missing: ${config.ollama.model}`);
    })
  );

  results.push(
    await check("Ollama chat", async () => {
      const answer = await chat("ollama", config.ollama.model, [
        { role: "system", content: "Reply with one word only." },
        { role: "user", content: "ok?" },
      ]);
      assert.ok(answer.trim().length > 0, "Empty Ollama answer");
    })
  );

  results.push(
    await check("File search by name and content", async () => {
      const targetDir = config.searchRoots.find((entry) => fs.existsSync(entry));
      assert.ok(targetDir, "No valid search root available");
      const filePath = path.join(targetDir, "gptbot-selftest-search.txt");
      fs.writeFileSync(filePath, "unique_grep_phrase_90210", "utf8");

      const find = await handleAssistantInput(500, "/find gptbot-selftest-search");
      const grep = await handleAssistantInput(500, "/grep unique_grep_phrase_90210");

      assert.ok(find.text.includes("gptbot-selftest-search.txt"), "Find command did not return the file");
      assert.ok(grep.text.includes("unique_grep_phrase_90210"), "Grep command did not find the content");

      fs.unlinkSync(filePath);
    })
  );

  results.push(
    await check("Windows list and screenshot", async () => {
      const list = await handleAssistantInput(501, "/windows");
      assert.ok(list.text.includes("Открытые окна"), "Windows list header missing");

      const shot = await handleAssistantInput(501, "/screenshot");
      assert.ok(shot.photoPath && fs.existsSync(shot.photoPath), "Screenshot file was not created");
      fs.unlinkSync(shot.photoPath);
    })
  );

  results.push(
    await check("Window focus/minimize/restore/type/enter", async () => {
      const outputPath = path.join(tmpDir, "pad-selftest.txt");
      if (fs.existsSync(outputPath)) {
        fs.unlinkSync(outputPath);
      }

      await startTestPad("GPTBOTPAD_SELFTEST", outputPath);

      await handleAssistantInput(502, "/focus GPTBOTPAD_SELFTEST");
      await sleep(300);
      await handleAssistantInput(502, "/minimize GPTBOTPAD_SELFTEST");
      await sleep(300);
      await handleAssistantInput(502, "/restore GPTBOTPAD_SELFTEST");
      await sleep(500);
      await handleAssistantInput(502, "/focus GPTBOTPAD_SELFTEST");
      await sleep(400);
      await handleAssistantInput(502, "/type hello + ^ % { } [ ]");
      await sleep(300);
      await handleAssistantInput(502, "/keys enter");
      await sleep(300);
      await handleAssistantInput(502, "/type line2");
      await sleep(800);

      assert.ok(fs.existsSync(outputPath), "Pad output file missing");
      const content = fs.readFileSync(outputPath, "utf8");
      assert.ok(content.includes("hello + ^ % { } [ ]"), `Pad text content mismatch: ${content}`);
      assert.ok(content.includes("line2"), `Pad second line missing: ${content}`);
    })
  );

  results.push(
    await check("Mouse click moves cursor", async () => {
      const before = await queryCursor();
      await handleAssistantInput(503, "/click 10 10");
      await sleep(300);
      const after = await queryCursor();
      assert.strictEqual(after.X, 10, `Cursor X mismatch: ${after.X}`);
      assert.strictEqual(after.Y, 10, `Cursor Y mismatch: ${after.Y}`);
      await handleAssistantInput(503, `/click ${before.X} ${before.Y}`);
    })
  );

  results.push(
    await check("Draft email and event fallback", async () => {
      const mail = await handleAssistantInput(504, "/mail test@example.com|Self test|Body");
      const event = await handleAssistantInput(504, "/event Demo|2026-06-27 14:00|30|Desk|Body");

      assert.ok(
        /Email draft created|черновик письма|Outlook/i.test(mail.text),
        `Unexpected mail result: ${mail.text}`
      );
      assert.ok(
        /Calendar event created|ICS|Outlook/i.test(event.text),
        `Unexpected event result: ${event.text}`
      );
    })
  );

  results.push(
    await check("Voice transcription", async () => {
      const mp3Path = path.join(tmpDir, "voice-selftest.mp3");
      if (fs.existsSync(mp3Path)) {
        fs.unlinkSync(mp3Path);
      }

      await generateVoiceTestMp3(mp3Path);
      const text = await transcribeAudio(mp3Path);
      assert.ok(/тест|голос/i.test(text), `Unexpected transcription: ${text}`);
      fs.unlinkSync(mp3Path);
    })
  );

  results.push(
    await check("History and reset", async () => {
      await handleAssistantInput(505, "/provider codexsale");
      await handleAssistantInput(505, `/model ${config.codexSale.model}`);
      const a1 = await handleAssistantInput(505, "Reply with one word: first");
      const a2 = await handleAssistantInput(505, "Reply with one word: second");
      assert.ok(a1.text.trim().length > 0, "First response empty");
      assert.ok(a2.text.trim().length > 0, "Second response empty");
      const reset = await handleAssistantInput(505, "/reset");
      assert.ok(/очищена/i.test(reset.text), `Reset message mismatch: ${reset.text}`);
    })
  );

  const failed = results.filter((item) => !item.ok);
  log("\n=== SUMMARY ===");
  log(`Passed: ${results.length - failed.length}`);
  log(`Failed: ${failed.length}`);

  if (failed.length > 0) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
