"""Persistent document counters. Allocations belong to the caller's transaction."""
import re
from collections.abc import Iterable

from sqlalchemy import BigInteger, String, func, select, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.base_class import Base


class DocumentCounter(Base):
    __tablename__ = "document_counters"
    scope: Mapped[str] = mapped_column(String(30), primary_key=True)
    value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


def numeric_order_base(number: str) -> int:
    match = re.fullmatch(r"(\d+(?: \d+)*)(?:[ -]?[A-Za-zА-Яа-яЁё]{1,3})?", number.strip())
    return int(match[1].replace(" ", "")) if match else 0


def highest(scope: str, numbers: Iterable[str | None]) -> int:
    if scope == "orders":
        return max((numeric_order_base(n or "") for n in numbers), default=0)
    return max((int(n[2:]) for n in numbers if n and re.fullmatch(r"З-\d+", n)), default=0)


def peek(db: Session, scope: str) -> int:
    from app.modules.leads.models import Lead
    from app.modules.orders.models import Order
    column = Order.order_number if scope == "orders" else Lead.lead_number
    floor = highest(scope, db.scalars(select(column)))
    saved = db.scalar(select(DocumentCounter.value).where(DocumentCounter.scope == scope)) or 0
    return max(saved, floor) + 1


def reserve(db: Session, scope: str, value: int) -> None:
    # Both supported backends provide an atomic upsert; no SELECT-then-INSERT race.
    if db.bind.dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        from sqlalchemy.dialects.postgresql import insert
    statement = insert(DocumentCounter).values(scope=scope, value=value)
    db.execute(statement.on_conflict_do_update(
        index_elements=[DocumentCounter.scope],
        set_={"value": func.max(DocumentCounter.value, value) if db.bind.dialect.name == "sqlite"
              else func.greatest(DocumentCounter.value, value)},
    ))


def allocate(db: Session, scope: str) -> int:
    reserve(db, scope, peek(db, scope) - 1)
    return db.scalar(update(DocumentCounter).where(DocumentCounter.scope == scope)
                     .values(value=DocumentCounter.value + 1).returning(DocumentCounter.value))
