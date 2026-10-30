"""
Integrations:
- Email (SMTP)
- Local calendar files
- Local notes
"""

import smtplib
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


class EmailService:
    def __init__(self, smtp_server: str, smtp_port: int, email: str, password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.email = email
        self.password = password

    def send_email(self, to: str, subject: str, body: str, files: list[str] | None = None) -> tuple[bool, str]:
        try:
            msg = MIMEMultipart()
            msg["From"] = self.email
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))

            for file_path in files or []:
                path = Path(file_path)
                if not path.exists():
                    continue
                with path.open("rb") as attachment:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f"attachment; filename={path.name}")
                    msg.attach(part)

            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email, self.password)
            server.send_message(msg)
            server.quit()

            suffix = f" + {len(files)} file(s)" if files else ""
            return True, f"Email sent to {to}{suffix}"
        except smtplib.SMTPAuthenticationError:
            return False, "SMTP authentication failed"
        except Exception as exc:
            return False, f"Email send error: {exc}"


class CalendarService:
    def __init__(self, calendar_dir: Path):
        self.calendar_dir = calendar_dir
        self.calendar_dir.mkdir(parents=True, exist_ok=True)

    def add_event(self, title: str, description: str = "", date_str: str | None = None) -> tuple[bool, str]:
        try:
            date_str = date_str or datetime.now().isoformat()
            event_id = int(datetime.now().timestamp())
            ics = (
                "BEGIN:VCALENDAR\n"
                "VERSION:2.0\n"
                "PRODID:-//OpenClaw//Events//EN\n"
                "BEGIN:VEVENT\n"
                f"UID:{event_id}\n"
                f"DTSTAMP:{datetime.now().isoformat()}\n"
                f"DTSTART:{date_str}\n"
                f"SUMMARY:{title}\n"
                f"DESCRIPTION:{description}\n"
                "END:VEVENT\n"
                "END:VCALENDAR\n"
            )
            out_file = self.calendar_dir / f"event_{event_id}.ics"
            out_file.write_text(ics, encoding="utf-8")
            return True, f"Event '{title}' added"
        except Exception as exc:
            return False, f"Calendar add error: {exc}"

    def list_events(self, days_ahead: int = 7) -> tuple[bool, str]:
        try:
            cutoff_ts = datetime.now().timestamp() - (days_ahead * 24 * 3600)
            files = sorted(
                self.calendar_dir.glob("event_*.ics"),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
            recent = [item for item in files if item.stat().st_mtime >= cutoff_ts][:20]
            if not recent:
                return True, f"No local events for last {days_ahead} day(s)"
            lines = [f"Events ({days_ahead} day window):"]
            lines.extend(f"- {item.name}" for item in recent)
            return True, "\n".join(lines)
        except Exception as exc:
            return False, f"Calendar list error: {exc}"


class NotesService:
    def __init__(self, notes_dir: Path):
        self.notes_dir = notes_dir
        self.notes_dir.mkdir(parents=True, exist_ok=True)

    def create_note(self, title: str, content: str, tags: list[str] | None = None) -> tuple[bool, str]:
        try:
            tags = tags or []
            safe_title = "".join(ch for ch in title if ch.isalnum() or ch in " -_").strip()[:50] or "note"
            out_file = self.notes_dir / f"{safe_title}_{int(datetime.now().timestamp())}.md"
            rendered = (
                f"# {title}\n\n"
                f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Tags: {', '.join(tags) if tags else 'none'}\n\n"
                "---\n\n"
                f"{content}\n"
            )
            out_file.write_text(rendered, encoding="utf-8")
            return True, f"Note '{title}' saved"
        except Exception as exc:
            return False, f"Note create error: {exc}"

    def list_notes(self, limit: int = 10) -> list[str]:
        try:
            notes = sorted(
                self.notes_dir.glob("*.md"),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )[:limit]
            return [item.name for item in notes]
        except Exception:
            return []
