from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.clients.models import Client
from app.modules.clients.phones import digits_only, phone_digits_expr, phone_variants

# Короткие «номера» (внутренний добавочный, обрывок ввода) слишком легко
# совпадают с чужими, поэтому по ним заявку к клиенту не привязываем.
MIN_PHONE_DIGITS = 5


class ClientRepository:
    @staticmethod
    def get_by_id(db: Session, client_id: uuid.UUID) -> Client | None:
        return db.get(Client, client_id)

    @staticmethod
    def find_by_contact(db: Session, email: str | None, phone: str | None) -> Client | None:
        conditions = []
        if email:
            # Почта регистронезависима: «Ivan@Mail.ru» и «ivan@mail.ru» — один клиент.
            conditions.append(func.lower(Client.email) == email.strip().lower())
        if phone:
            digits = digits_only(phone)
            if len(digits) >= MIN_PHONE_DIGITS:
                stored_digits = phone_digits_expr()
                conditions.extend(stored_digits == variant for variant in phone_variants(digits))
            else:
                conditions.append(Client.phone == phone)
        if not conditions:
            return None
        # Совпасть может несколько записей — берём самую раннюю, чтобы история
        # заказов собиралась на первом заведённом клиенте, а не на дубле.
        return db.scalar(select(Client).where(or_(*conditions)).order_by(Client.created_at.asc()))
