from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.sqlite_unicode import install_unicode_case_functions

settings = get_settings()

is_sqlite = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}
# Портативная файловая SQLite обслуживает короткие запросы. Очередь из 15
# соединений удерживала десятки параллельных чтений и давала 500 по таймауту;
# отдельное соединение на запрос освобождается сразу после закрытия Session.
sqlite_database = make_url(settings.database_url).database if is_sqlite else None
pool_options = (
    {"poolclass": NullPool} if is_sqlite and sqlite_database not in (None, "", ":memory:") else {}
)

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
    connect_args=connect_args,
    **pool_options,
)
install_unicode_case_functions(engine)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
