"""Юникодный ``lower()`` и ``upper()`` для SQLite.

Встроенные функции SQLite меняют регистр только у латиницы: `lower('Кузнецов')`
возвращает `'Кузнецов'` без изменений. Поэтому любой поиск вида
``func.lower(column).like('%кузнецов%')`` на SQLite не находит русские слова,
хотя на PostgreSQL работает правильно.

Расхождение опасно тем, что оно тихое: разработка идёт на SQLite и поиск
выглядит сломанным, прод на PostgreSQL — и там всё в порядке. Регистрируем
питоновские реализации, чтобы поведение совпадало на обеих базах.
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.engine import Engine


def _register(dbapi_connection: object, _record: object) -> None:
    create_function = getattr(dbapi_connection, "create_function", None)
    if create_function is None:
        return

    def unicode_lower(value: str | None) -> str | None:
        return value.lower() if isinstance(value, str) else value

    def unicode_upper(value: str | None) -> str | None:
        return value.upper() if isinstance(value, str) else value

    # deterministic=True разрешает использование функции в индексах и WHERE;
    # аргумент появился в Python 3.8, проект требует 3.12.
    create_function("lower", 1, unicode_lower, deterministic=True)
    create_function("upper", 1, unicode_upper, deterministic=True)


def install_unicode_case_functions(engine: Engine) -> None:
    """Подключает юникодные lower/upper, если движок — SQLite."""
    if engine.dialect.name != "sqlite":
        return
    event.listen(engine, "connect", _register)
