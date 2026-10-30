from __future__ import annotations

import re
import uuid
from decimal import Decimal

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import PageParams, pagination_meta
from app.modules.audit.service import AuditService
from app.modules.price_book.kinds import kind_label, unit_label
from app.modules.price_book.models import PriceItem, PriceItemChange
from app.modules.price_book.schemas import (
    PriceItemCreate,
    PriceItemDetailRead,
    PriceItemRead,
    PriceItemUpdate,
)


class PriceBookService:
    @staticmethod
    def delete_item(db: Session, item_id: uuid.UUID, acting_user_id=None) -> None:
        from app.modules.orders.models import OrderPosition

        item = PriceBookService.get_item(db, item_id)
        try:
            # Order positions already contain their own article, dimensions and prices.
            # Only detach the optional catalogue reference; never recalculate old orders.
            db.execute(update(OrderPosition).where(OrderPosition.price_item_id == item_id)
                       .values(price_item_id=None), execution_options={"synchronize_session": False})
            AuditService.log_event(db, entity_type="price_item", entity_id=str(item_id),
                                  action="delete_price_item", user_id=acting_user_id,
                                  old_value={"article": item.article, "name": item.name, "kind": item.kind, "price": item.price})
            db.delete(item)
            db.commit()
            db.expire_all()
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _normalize_article(article: str) -> str:
        """Артикул без обрамляющих пробелов, приставки «арт.» и в верхнем регистре.

        Менеджер вводит «фр-01», «ФР-01 » и «ФР-01» как один и тот же артикул.
        Без нормализации в справочнике окажутся три записи с разной ценой.

        Приставку «арт.» срезаем, а описание после номера отбрасываем: заказчик
        просил дословно, чтобы «арт. 112 пвх эмаль попаписякака» превращалось в
        «112» — покрытие и так хранится типом позиции, в номере ему не место.

        Отбрасываем только словесный хвост: остаток отсекается, если все
        оставшиеся слова без цифр. Составной номер вроде «ФР 01» остаётся
        целым — иначе разные позиции слились бы в одну.
        """
        # Приставку снимаем только перед номером. Без этого «арт» съедалось и у
        # слова «артикул»: «артикул 113» превращалось в «ИКУЛ 113» — именно так
        # заказчик и пишет фрезеровку в бланке.
        cleaned = re.sub(
            r"^\s*(?:артикул|арт|article|art)[\.\s№]*(?=\d)",
            "",
            article,
            flags=re.IGNORECASE,
        )
        parts = cleaned.split()
        if len(parts) > 1 and not any(char.isdigit() for word in parts[1:] for char in word):
            cleaned = parts[0]
        return cleaned.strip().upper()

    @staticmethod
    def to_read(item: PriceItem) -> PriceItemRead:
        data = PriceItemRead.model_validate(item)
        data.kind_label = kind_label(item.kind)
        data.unit_label = unit_label(item.unit)
        return data

    @staticmethod
    def to_detail(item: PriceItem) -> PriceItemDetailRead:
        data = PriceItemDetailRead.model_validate(item)
        data.kind_label = kind_label(item.kind)
        data.unit_label = unit_label(item.unit)
        return data

    @staticmethod
    def list_items(
        db: Session,
        params: PageParams,
        *,
        search: str | None = None,
        kind: str | None = None,
        only_active: bool = False,
    ) -> tuple[list[PriceItem], dict[str, object]]:
        stmt = select(PriceItem)
        count_stmt = select(func.count()).select_from(PriceItem)

        if search:
            pattern = f"%{search.strip()}%"
            condition = or_(PriceItem.article.ilike(pattern), PriceItem.name.ilike(pattern))
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
        if kind:
            stmt = stmt.where(PriceItem.kind == kind)
            count_stmt = count_stmt.where(PriceItem.kind == kind)
        if only_active:
            stmt = stmt.where(PriceItem.is_active.is_(True))
            count_stmt = count_stmt.where(PriceItem.is_active.is_(True))

        total = db.scalar(count_stmt) or 0
        stmt = (
            stmt.order_by(PriceItem.sort_order.asc(), PriceItem.article.asc())
            .offset(params.offset)
            .limit(params.size)
        )
        return list(db.scalars(stmt).all()), pagination_meta(total, params)

    @staticmethod
    def get_item(db: Session, item_id: uuid.UUID) -> PriceItem:
        item = db.scalar(
            select(PriceItem)
            .options(selectinload(PriceItem.price_changes))
            .where(PriceItem.id == item_id)
        )
        if not item:
            raise NotFoundError("Артикул не найден")
        return item

    @staticmethod
    def get_by_article(db: Session, article: str, kind: str | None = None) -> PriceItem | None:
        """Артикул по номеру. С типом — ровно та позиция, без типа — любая.

        Без типа зовут старые места, которым достаточно первой подходящей: там
        номер приходит из уже сохранённой строки заказа, где тип записан рядом.
        """
        normalized = PriceBookService._normalize_article(article)
        stmt = select(PriceItem).where(PriceItem.article == normalized)
        if kind:
            stmt = stmt.where(PriceItem.kind == kind)
        return db.scalars(stmt.order_by(PriceItem.created_at.asc())).first()

    @staticmethod
    def create_item(
        db: Session,
        payload: PriceItemCreate,
        acting_user_id: uuid.UUID | None = None,
        *,
        commit: bool = True,
    ) -> PriceItem:
        article = PriceBookService._normalize_article(payload.article)
        if not article:
            raise ConflictError("Артикул не может быть пустым")
        if PriceBookService.get_by_article(db, article, payload.kind):
            raise ConflictError(f"Артикул «{article}» уже есть в типе «{kind_label(payload.kind)}»")

        values = payload.model_dump()
        values["article"] = article
        item = PriceItem(**values)
        db.add(item)
        db.flush()

        # Первая цена тоже попадает в историю: иначе в карточке артикула пустой
        # список и непонятно, с чего начинали.
        db.add(
            PriceItemChange(
                price_item_id=item.id,
                old_price=Decimal("0"),
                new_price=item.price,
                comment="Артикул заведён",
                changed_by=acting_user_id,
            )
        )
        AuditService.log_event(
            db,
            entity_type="price_item",
            entity_id=str(item.id),
            action="create_price_item",
            user_id=str(acting_user_id) if acting_user_id else None,
            new_value={"article": item.article, "price": str(item.price)},
        )
        if commit:
            db.commit()
        else:
            db.flush()
        return PriceBookService.get_item(db, item.id)

    @staticmethod
    def update_item(
        db: Session,
        item_id: uuid.UUID,
        payload: PriceItemUpdate,
        acting_user_id: uuid.UUID | None = None,
    ) -> PriceItem:
        item = PriceBookService.get_item(db, item_id)
        changes = payload.model_dump(exclude_unset=True)
        price_comment = changes.pop("price_comment", None)
        old_price = item.price

        if "article" in changes:
            article = PriceBookService._normalize_article(changes["article"] or "")
            if not article:
                raise ConflictError("Артикул не может быть пустым")
            changes["article"] = article
        target_kind = changes.get("kind", item.kind)
        target_article = changes.get("article", item.article)
        if target_kind != item.kind or target_article != item.article:
            duplicate = PriceBookService.get_by_article(db, target_article, target_kind)
            if duplicate and duplicate.id != item.id:
                raise ConflictError(
                    f"Артикул «{target_article}» уже есть в типе «{kind_label(target_kind)}»"
                )

        old_values = {
            "article": item.article,
            "name": item.name,
            "kind": item.kind,
            "unit": item.unit,
            "price": str(item.price),
        }

        for key, value in changes.items():
            setattr(item, key, value)

        new_price = item.price
        if new_price != old_price:
            # Новая цена действует только на будущие заказы: у уже созданных
            # позиций своя копия цены, и трогать её нельзя — иначе прошлые
            # месяцы задним числом изменят выручку.
            db.add(
                PriceItemChange(
                    price_item_id=item.id,
                    old_price=old_price,
                    new_price=new_price,
                    comment=price_comment,
                    changed_by=acting_user_id,
                )
            )

        AuditService.log_event(
            db,
            entity_type="price_item",
            entity_id=str(item.id),
            action="update_price_item",
            user_id=str(acting_user_id) if acting_user_id else None,
            old_value=old_values,
            new_value={
                "article": item.article,
                "name": item.name,
                "kind": item.kind,
                "unit": item.unit,
                "price": str(new_price),
            },
        )
        db.commit()
        return PriceBookService.get_item(db, item.id)
