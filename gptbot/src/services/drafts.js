const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const config = require("../config");
const { ensureDir } = require("../utils");

const draftsDir = path.join(config.dataDir, "drafts");
ensureDir(draftsDir);

function sanitizeName(value) {
  return String(value || "draft")
    .replace(/[<>:"/\\|?*\x00-\x1F]/g, "_")
    .slice(0, 80);
}

function createEmailDraftFile({ to, subject, body }) {
  const timestamp = Date.now();
  const fileName = `${timestamp}-${sanitizeName(subject || to || "email")}.txt`;
  const filePath = path.join(draftsDir, fileName);
  const content = [
    `To: ${to}`,
    `Subject: ${subject}`,
    "",
    body || "",
  ].join("\n");

  fs.writeFileSync(filePath, content, "utf8");
  return filePath;
}

function formatIcsDate(date) {
  const pad = (value) => String(value).padStart(2, "0");
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
    "T",
    pad(date.getHours()),
    pad(date.getMinutes()),
    pad(date.getSeconds()),
  ].join("");
}

function createCalendarEventFile({ title, start, minutes, location, body }) {
  const startDate = new Date(start);
  const durationMinutes = Number.parseInt(minutes, 10) || 60;
  const endDate = new Date(startDate.getTime() + durationMinutes * 60 * 1000);
  const uid = crypto.randomUUID();
  const timestamp = Date.now();
  const fileName = `${timestamp}-${sanitizeName(title || "event")}.ics`;
  const filePath = path.join(draftsDir, fileName);
  const content = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//gptbot//Telegram Desktop Assistant//RU",
    "BEGIN:VEVENT",
    `UID:${uid}`,
    `DTSTAMP:${formatIcsDate(new Date())}`,
    `DTSTART:${formatIcsDate(startDate)}`,
    `DTEND:${formatIcsDate(endDate)}`,
    `SUMMARY:${title || "Event"}`,
    `LOCATION:${location || ""}`,
    `DESCRIPTION:${(body || "").replace(/\r?\n/g, "\\n")}`,
    "END:VEVENT",
    "END:VCALENDAR",
    "",
  ].join("\r\n");

  fs.writeFileSync(filePath, content, "utf8");
  return filePath;
}

module.exports = {
  createEmailDraftFile,
  createCalendarEventFile,
};
