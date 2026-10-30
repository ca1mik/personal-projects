from dataclasses import dataclass
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()

def _split_ints(v: str) -> set[int]:
    v = (v or "").strip()
    if not v:
        return set()
    out = set()
    for x in v.split(","):
        x = x.strip()
        if x:
            out.add(int(x))
    return out

def _split_csv(v: str) -> list[str]:
    raw = (v or "").strip()
    if not raw:
        return []
    out: list[str] = []
    for part in raw.split(","):
        item = part.strip()
        if item:
            out.append(item)
    return out

@dataclass(frozen=True)
class Config:
    token: str
    allowed_user_ids: set[int]
    allowed_chat_ids: set[int]
    workdir: Path
    db_path: Path
    confirm_ttl: int
    # Интеграции
    calendar_dir: Path
    notes_dir: Path
    email_smtp_server: str
    email_smtp_port: int
    email_address: str
    email_password: str
    enable_nlu: bool  # Включить умный анализ текста
    # Google интеграции
    google_credentials_path: Path
    use_google_calendar: bool
    use_google_notes: bool
    use_google_sheets_memory: bool
    google_memory_sheet_id: str
    proactive_research_enabled: bool
    proactive_research_interval_minutes: int
    proactive_research_send_to_chat: bool
    proactive_topics: list[str]

def load_config() -> Config:
    token = os.getenv("TG_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TG_BOT_TOKEN is missing in .env")

    workdir = Path(os.getenv("WORKDIR", r"C:\open-claw-workdir"))
    workdir.mkdir(parents=True, exist_ok=True)

    db_path = Path(os.getenv("DB_PATH", "claw.db"))
    confirm_ttl = int(os.getenv("CONFIRM_TTL", "60"))
    
    # Директории для интеграций
    calendar_dir = Path(os.getenv("CALENDAR_DIR", str(workdir / "calendar")))
    notes_dir = Path(os.getenv("NOTES_DIR", str(workdir / "notes")))
    calendar_dir.mkdir(parents=True, exist_ok=True)
    notes_dir.mkdir(parents=True, exist_ok=True)
    
    # Email параметры
    email_smtp_server = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
    email_smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    email_address = os.getenv("EMAIL_ADDRESS", "")
    email_password = os.getenv("EMAIL_PASSWORD", "")
    
    # NLU опция
    enable_nlu = os.getenv("ENABLE_NLU", "true").lower() in ["true", "1", "yes"]
    
    # Google интеграции
    google_credentials_path = Path(os.getenv("GOOGLE_CREDENTIALS_PATH", workdir / "credentials.json"))
    use_google_calendar = os.getenv("USE_GOOGLE_CALENDAR", "false").lower() in ["true", "1", "yes"]
    use_google_notes = os.getenv("USE_GOOGLE_NOTES", "false").lower() in ["true", "1", "yes"]
    use_google_sheets_memory = os.getenv("USE_GOOGLE_SHEETS_MEMORY", "false").lower() in ["true", "1", "yes"]
    google_memory_sheet_id = os.getenv("GOOGLE_MEMORY_SHEET_ID", "").strip()
    proactive_research_enabled = os.getenv("PROACTIVE_RESEARCH_ENABLED", "false").lower() in ["true", "1", "yes"]
    proactive_research_interval_minutes = int(os.getenv("PROACTIVE_RESEARCH_INTERVAL_MINUTES", "180"))
    proactive_research_send_to_chat = os.getenv("PROACTIVE_RESEARCH_SEND_TO_CHAT", "false").lower() in ["true", "1", "yes"]
    proactive_topics = _split_csv(os.getenv("PROACTIVE_TOPICS", "ai tools,market trends,business models"))

    return Config(
        token=token,
        allowed_user_ids=_split_ints(os.getenv("ALLOWED_USER_IDS", "")),
        allowed_chat_ids=_split_ints(os.getenv("ALLOWED_CHAT_IDS", "")),
        workdir=workdir,
        db_path=db_path,
        confirm_ttl=confirm_ttl,
        calendar_dir=calendar_dir,
        notes_dir=notes_dir,
        email_smtp_server=email_smtp_server,
        email_smtp_port=email_smtp_port,
        email_address=email_address,
        email_password=email_password,
        enable_nlu=enable_nlu,
        google_credentials_path=google_credentials_path,
        use_google_calendar=use_google_calendar,
        use_google_notes=use_google_notes,
        use_google_sheets_memory=use_google_sheets_memory,
        google_memory_sheet_id=google_memory_sheet_id,
        proactive_research_enabled=proactive_research_enabled,
        proactive_research_interval_minutes=proactive_research_interval_minutes,
        proactive_research_send_to_chat=proactive_research_send_to_chat,
        proactive_topics=proactive_topics,
    )
