const fs = require("fs");
const path = require("path");
const config = require("../config");
const { runProcess } = require("./process");
const { transcribeAudio } = require("./ai");

async function downloadTelegramFile(bot, fileId) {
  const url = await bot.getFileLink(fileId);
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to download Telegram file: HTTP ${response.status}`);
  }

  const buffer = Buffer.from(await response.arrayBuffer());
  const sourcePath = path.join(config.tempDir, `${fileId}.ogg`);
  fs.writeFileSync(sourcePath, buffer);
  return sourcePath;
}

async function convertVoiceToMp3(sourcePath) {
  const targetPath = sourcePath.replace(/\.ogg$/i, ".mp3");
  const args = [
    "-y",
    "-i",
    sourcePath,
    "-vn",
    "-ac",
    "1",
    "-ar",
    "16000",
    "-codec:a",
    "libmp3lame",
    targetPath,
  ];

  const result = await runProcess("ffmpeg", args, {
    timeoutMs: 60000,
  });

  if (result.code !== 0) {
    throw new Error(result.stderr.trim() || "ffmpeg conversion failed");
  }

  return targetPath;
}

async function transcribeTelegramVoice(bot, voice) {
  const sourcePath = await downloadTelegramFile(bot, voice.file_id);
  let convertedPath = sourcePath;

  try {
    convertedPath = await convertVoiceToMp3(sourcePath);
    return await transcribeAudio(convertedPath);
  } finally {
    [sourcePath, convertedPath].forEach((filePath) => {
      if (filePath && fs.existsSync(filePath)) {
        fs.unlinkSync(filePath);
      }
    });
  }
}

module.exports = {
  transcribeTelegramVoice,
};
