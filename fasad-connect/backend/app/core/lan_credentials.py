"""Проверка известных демо-паролей перед открытием портативной сборки в сети."""

from __future__ import annotations

from sqlalchemy import select

from app.core.security import verify_password
from app.db.session import SessionLocal
from app.modules.users.models import User

DEMO_PASSWORDS = {
    "admin": "admin123",
    "manager": "manager123",
    "technologist": "tech123",
    "operator.cutting": "operator123",
    "operator.assembly": "operator123",
}


def main() -> int:
    try:
        with SessionLocal() as db:
            users = db.scalars(select(User).where(User.login.in_(DEMO_PASSWORDS))).all()
            exposed = [
                user.login
                for user in users
                if user.is_active
                and verify_password(DEMO_PASSWORDS[user.login], user.password_hash)
            ]
    except Exception as exc:
        print(f"Не удалось проверить пароли в базе: {exc}")
        return 2

    if exposed:
        print("Стандартные пароли ещё действуют: " + ", ".join(sorted(exposed)))
        print("Смените их в разделе Администрирование → Пользователи и перезапустите start.bat.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
