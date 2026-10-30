"""Смета заказа: строки с ценами и приход денег.

Вынесено из ``service.py``, потому что это отдельный разговор — не про
производство, а про деньги: что продали, почём и сколько уже заплатили.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, NotFoundError
from app.modules.audit.service import AuditService
from app.modules.leads.models import Lead
from app.modules.orders.models import Order, OrderPayment, OrderPosition
from app.modules.orders.money import round_order_amount
from app.modules.orders.payments import PAYMENT_METHODS, payment_method_label
from app.modules.orders.schemas import (
    OrderBalanceRead,
    OrderPaymentCreate,
    OrderPaymentRead,
    OrderPositionRead,
    OrderPositionsReplace,
    OrderPositionWrite,
)
from app.modules.price_book.kinds import (
    AREA_UNIT,
    direction_price_kind,
    kind_label,
    unit_label,
)
from app.modules.price_book.models import PriceItem
from app.modules.price_book.schemas import PriceItemCreate
from app.modules.price_book.service import PriceBookService

MM2_IN_SQM = Decimal("1000000")
MONEY = Decimal("0.01")


def _round_money(value: Decimal) -> Decimal:
    """Рубли и копейки, округление как в кассе — от 0.5 вверх."""
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


class OrderPositionService:
    @staticmethod
    def _require_order(db: Session, order_id: uuid.UUID) -> Order:
        order = db.get(Order, order_id)
        if not order or order.deleted_at:
            raise NotFoundError("Заказ не найден")
        return order

    @staticmethod
    def _area_of(row: OrderPositionWrite) -> Decimal:
        """Площадь строки в м².

        Размеры важнее присланной площади: если менеджер поправил длину, а
        площадь осталась старой, верить надо размерам — иначе в смете окажется
        цифра, которой не соответствует ни одна деталь.
        """
        if row.width and row.height:
            return (Decimal(row.width) * Decimal(row.height) * Decimal(row.quantity)) / MM2_IN_SQM
        if row.area_sqm is not None:
            return Decimal(row.area_sqm)
        return Decimal("0")

    @staticmethod
    def _adopt_new_article(
        db: Session,
        row: OrderPositionWrite,
        acting_user_id: uuid.UUID | None,
    ) -> PriceItem | None:
        """Заводит номенклатуру в справочник прямо из сметы.

        Заказчик: «пусть вводят номенклатуры сами... уже занося в заказ — она
        попадала бы в базу, именно той части, которую выбрали». Менеджер пишет
        номер и цену в строке заказа, выбрав тип, — и этот номер появляется в
        справочнике под этим типом. В следующий раз он найдётся поиском.

        Прежнее правило «из заказов в справочник ничего не попадает» отменено
        заказчиком осознанно: наполнять прайс отдельным экраном никто не стал
        бы, а без прайса цена не подставляется.

        Известный номер не трогаем: цена в нём могла быть согласована раньше, и
        сегодняшняя разовая скидка не должна становиться прайсом для всех — она
        остаётся индивидуальной ценой этой строки.
        """
        article = PriceBookService._normalize_article(row.article or "")
        if not article or row.unit_price is None:
            return None
        price = Decimal(row.unit_price)
        if price <= 0:
            return None

        existing = PriceBookService.get_by_article(db, article, row.kind)
        if existing:
            return existing

        return PriceBookService.create_item(
            db,
            PriceItemCreate(
                article=article,
                # Название по типу: заказчик просил, чтобы в артикуле были только
                # цифры, а покрытие читалось из типа, а не из названия.
                name=f"{kind_label(row.kind)}, арт. {article}",
                kind=row.kind,
                unit=row.unit,
                price=price,
                comment="Заведено из сметы заказа",
            ),
            acting_user_id=acting_user_id,
        )

    @staticmethod
    def _resolve_price(
        db: Session,
        row: OrderPositionWrite,
    ) -> tuple[PriceItem | None, Decimal, Decimal | None, bool]:
        """Цена строки: из справочника, своя под заказ или своя у нестандарта.

        Возвращает артикул, цену продажи, цену по прайсу и признак ручной
        правки.

        Заказчик: «пусть с базы подтягиваются, но при этом менеджер может сама
        корректировать их, не меняя в самой базе, просто по типу индивидуальных
        цен под заказ». Поэтому у артикульной строки цена подставляется из
        справочника, но присланная в запросе перебивает её — и тогда строка
        помечается как поправленная вручную. Сам справочник не двигается: цена
        для остальных заказов остаётся прежней.
        """
        if row.price_item_id is not None:
            item = db.get(PriceItem, row.price_item_id)
            if not item:
                raise NotFoundError("Артикул не найден в справочнике")
            if not item.is_active:
                raise AppError(f"Артикул «{item.article}» отключён в справочнике", 422)
            base_price = Decimal(item.price)
            if row.unit_price is None:
                return item, base_price, base_price, False
            manual = Decimal(row.unit_price)
            # Ноль руками — не «скидка 100 %», а незаполненное поле: строка
            # ушла бы в заказ бесплатной и молча занизила сумму.
            if manual <= 0:
                raise AppError(
                    f"Строка «{row.name}»: цена не может быть нулевой — "
                    "оставьте цену из справочника или напишите свою",
                    422,
                )
            return item, manual, base_price, manual != base_price

        if not row.is_custom:
            raise AppError(
                f"Строка «{row.name}»: выберите артикул из справочника "
                "или отметьте её как нестандарт",
                422,
            )
        if row.unit_price is None:
            raise AppError(f"Строка «{row.name}»: у нестандарта нужна своя цена", 422)
        # У нестандарта прайсовой цены не существует, поэтому сравнивать не с
        # чем: ручной правкой это не считается.
        return None, Decimal(row.unit_price), None, False

    @staticmethod
    def to_read(position: OrderPosition) -> OrderPositionRead:
        data = OrderPositionRead.model_validate(position)
        data.kind_label = kind_label(position.kind)
        data.unit_label = unit_label(position.unit)
        return data

    @staticmethod
    def replace_positions(
        db: Session,
        order_id: uuid.UUID,
        payload: OrderPositionsReplace,
        acting_user_id: uuid.UUID | None = None,
    ) -> list[OrderPosition]:
        order = OrderPositionService._require_order(db, order_id)

        # Таблица приходит целиком, поэтому старые строки удаляются, а не
        # обновляются: сопоставлять их по id пришлось бы на фронте, а там
        # строку можно и удалить, и вставить в середину.
        for existing in list(order.positions):
            db.delete(existing)
        db.flush()

        created: list[OrderPosition] = []
        for index, row in enumerate(payload.positions, start=1):
            # Менеджер написал номер и цену, но артикул из справочника не
            # выбирал — значит это новая номенклатура. Заводим её под выбранным
            # типом и дальше считаем строку как обычную артикульную.
            if row.price_item_id is None and not row.is_custom and row.article:
                adopted = OrderPositionService._adopt_new_article(db, row, acting_user_id)
                if adopted:
                    row = row.model_copy(update={"price_item_id": adopted.id})

            price_item, unit_price, base_price, overridden = OrderPositionService._resolve_price(
                db, row
            )
            area = OrderPositionService._area_of(row)
            # Единица — та, что реально сохранится в строке: у артикула она своя,
            # из справочника, и присланная в запросе её не отменяет. Иначе цена
            # «за штуку» умножилась бы на площадь и заказ посчитался бы не по
            # тому основанию, а в таблице стояла бы подпись «шт».
            unit = price_item.unit if price_item else row.unit
            base = area if unit == AREA_UNIT else Decimal(row.quantity)
            if unit_price > 0 and base <= 0:
                # Цена есть, а умножать не на что: строка ушла бы в заказ нулём и
                # занизила сумму, причём молча — это дороже отказа сохранить.
                reason = "не заданы размеры" if unit == AREA_UNIT else "не задано количество"
                raise AppError(
                    f"Строка «{row.name}»: цена указана, но {reason} — "
                    "строка добавила бы к заказу 0 ₽",
                    422,
                )
            position = OrderPosition(
                order_id=order.id,
                line_no=index,
                price_item_id=price_item.id if price_item else None,
                is_custom=price_item is None,
                # Артикул копируется строкой: если позже его переименуют в
                # справочнике, в старом заказе останется то, что продавали.
                # Набранный руками чистим тем же правилом, что и справочник:
                # иначе «арт. 112» в заказе и «112» в справочнике — разные
                # артикулы, и подсказки по ним расходятся.
                article=(
                    price_item.article
                    if price_item
                    else (PriceBookService._normalize_article(row.article) if row.article else None)
                ),
                name=row.name.strip(),
                kind=(price_item.kind if price_item else row.kind),
                unit=unit,
                quantity=Decimal(row.quantity),
                width=row.width,
                height=row.height,
                area_sqm=area,
                unit_price=unit_price,
                price_overridden=overridden,
                base_price=base_price,
                amount=_round_money(row.amount_override if row.amount_override is not None else unit_price * base),
                thickness=row.thickness,
                color=row.color,
                milling=row.milling,
                comment=row.comment,
            )
            db.add(position)
            created.append(position)

        db.flush()
        OrderPositionService._apply_totals(order, created)
        AuditService.log_event(
            db,
            entity_type="order",
            entity_id=str(order.id),
            action="replace_order_positions",
            user_id=str(acting_user_id) if acting_user_id else None,
            new_value={"lines": len(created), "total": str(order.total_amount)},
        )
        db.commit()

        if order.direction and order.direction.code == "pvc":
            from app.modules.orders.auto_film_layout import save_for_order

            save_for_order(db, order.id, acting_user_id)

        return list(
            db.scalars(
                select(OrderPosition)
                .where(OrderPosition.order_id == order.id)
                .order_by(OrderPosition.line_no.asc())
            ).all()
        )

    @staticmethod
    def _apply_totals(order: Order, positions: list[OrderPosition]) -> None:
        """Сумма заказа = сумма строк сметы минус скидка.

        Скидку менеджер ставит отдельно, она пересчёту по строкам не подлежит.
        """
        total = _round_money(sum((item.amount for item in positions), Decimal("0")))
        order.total_amount = total
        order.final_amount = round_order_amount(total - Decimal(order.discount_amount or 0))


class LeadEstimateTransfer:
    """Перенос посчитанной заявки в смету заказа.

    Заказчик считает клиенту цену прямо в заявке, в той же таблице, что уходит
    в цех на бумаге. Когда заявка становится заказом, эти строки обязаны
    перейти в смету — иначе менеджер вводит их второй раз и ошибается.

    Цена переносится **как есть**, копией: она уже была названа клиенту. Даже
    если справочник за это время подорожал, заказ уходит по той цене, о которой
    договаривались.
    """

    @staticmethod
    def read_lead_parts(lead: Lead) -> list[dict]:
        """Позиции заявки из того же места, где их читают печать и раскрой."""
        payload = lead.parsed_payload_json or {}
        raw = payload.get("raw_payload") or {}
        parts = raw.get("parts")
        if not isinstance(parts, list):
            return []
        return [item for item in parts if isinstance(item, dict)]

    @staticmethod
    def main_work_kind(lead: Lead) -> str | None:
        """Основная ОПЕРАЦИЯ заявки — та, которой в ней больше всего.

        Нужна для буквы в номере заказа: заказчик просил, чтобы она зависела «от
        фрезы, мыла, шпона». В заявке операций может быть несколько (фрезеровка и
        мыло в одном заказе), а номер один — берём преобладающую, при равенстве
        первую по порядку строк, как менеджер их и заносил.

        Строки, повторяющие само направление, в голосовании не участвуют. У
        заявки «Эмаль» тип работ `paint` стоит у обычных фасадов и ничего нового
        не сообщает: направление и так эмаль. Пока такие строки голосовали
        наравне с операциями, буква зависела от их количества — две строки
        фрезеровки и три обычные давали голый номер, а две и одна давали «-Ф».
        Менеджер дописал артикул руками — и номер заказа сменился.
        """
        own_kind = direction_price_kind(lead.direction.code) if lead.direction else ""
        counts: dict[str, int] = {}
        for row in LeadEstimateTransfer.read_lead_parts(lead):
            kind = str(row.get("kind") or "").strip()
            if kind and kind != own_kind:
                counts[kind] = counts.get(kind, 0) + 1
        if not counts:
            return None
        return max(counts, key=lambda code: counts[code])

    @staticmethod
    def _decimal(value: object, default: str = "0") -> Decimal:
        try:
            return Decimal(str(value))
        except (ArithmeticError, TypeError, ValueError):
            return Decimal(default)

    @staticmethod
    def copy_to_order(
        db: Session,
        lead: Lead,
        order: Order,
        acting_user_id: uuid.UUID | None = None,
    ) -> list[OrderPosition]:
        """Строки заявки с ценой становятся строками сметы заказа.

        Позиции без цены не переносятся: в смете строка за 0 ₽ занизила бы
        сумму заказа, а менеджер этого не заметил бы. Размеры такой заявки
        никуда не деваются — они остаются в заявке и в раскрое.
        """
        rows = [
            item
            for item in LeadEstimateTransfer.read_lead_parts(lead)
            if LeadEstimateTransfer._decimal(item.get("unit_price")) > 0
            or item.get("amount_override") is not None
        ]
        if not rows:
            return []

        created: list[OrderPosition] = []
        for index, row in enumerate(rows, start=1):
            width = LeadEstimateTransfer._decimal(row.get("width"))
            height = LeadEstimateTransfer._decimal(row.get("height"))
            quantity = LeadEstimateTransfer._decimal(row.get("quantity"), "1")
            area = LeadEstimateTransfer._decimal(row.get("area_sqm"))
            if area <= 0:
                area = (width * height * quantity) / MM2_IN_SQM

            unit = str(row.get("unit") or AREA_UNIT)
            unit_price = LeadEstimateTransfer._decimal(row.get("unit_price"))
            explicit_amount = row.get("amount_override")
            amount = LeadEstimateTransfer._decimal(explicit_amount if explicit_amount is not None else row.get("amount"))
            if amount <= 0 and explicit_amount is None:
                base = area if unit == AREA_UNIT else quantity
                amount = unit_price * base

            article = row.get("article")
            kind = str(row.get("kind") or "other")
            price_item = (
                PriceBookService.get_by_article(db, str(article), kind) if article else None
            )
            # Номенклатуры ещё нет в справочнике — заводим её здесь. Заказчик:
            # «занося в заказ — она попадала бы в базу, именно той части,
            # которую выбрали». Тип берём из строки заявки: менеджер выбрал его
            # при приёме.
            if article and not price_item and unit_price > 0:
                normalized = PriceBookService._normalize_article(str(article))
                if normalized:
                    price_item = PriceBookService.create_item(
                        db,
                        PriceItemCreate(
                            article=normalized,
                            name=f"{kind_label(kind)}, арт. {normalized}",
                            kind=kind,
                            unit=unit,
                            price=unit_price,
                            comment="Заведено из заявки",
                        ),
                        acting_user_id=acting_user_id,
                    )
            name = str(row.get("milling") or "").strip() or (
                price_item.name if price_item else "Позиция из заявки"
            )

            position = OrderPosition(
                order_id=order.id,
                line_no=index,
                price_item_id=price_item.id if price_item else None,
                # Артикул мог исчезнуть из справочника между заявкой и заказом.
                # Строка всё равно переносится — как нестандарт с той же ценой,
                # потому что клиенту её уже назвали.
                is_custom=price_item is None,
                # Номер пишем нормализованным: менеджер мог набрать «арт. 112»,
                # а в справочнике и в печатной смете это должен быть один и тот
                # же 112-й, иначе строка заказа и справочник разойдутся.
                article=(
                    price_item.article
                    if price_item
                    else (PriceBookService._normalize_article(str(article)) if article else None)
                ),
                name=name[:255],
                kind=str(row.get("kind") or (price_item.kind if price_item else "other")),
                unit=unit,
                quantity=quantity,
                width=width or None,
                height=height or None,
                area_sqm=area,
                unit_price=unit_price,
                # Цена в заявке могла быть поправлена под клиента, а могла
                # просто прийти из прайса. Отличаем сравнением с прайсовой на
                # момент переноса: иначе в заказе не видно, что цена особая.
                price_overridden=bool(price_item and unit_price != Decimal(price_item.price)),
                base_price=Decimal(price_item.price) if price_item else None,
                amount=_round_money(amount),
                thickness=LeadEstimateTransfer._decimal(row.get("thickness")) or None,
                color=str(row.get("material")) if row.get("material") else None,
                milling=str(row.get("milling")) if row.get("milling") else None,
            )
            db.add(position)
            created.append(position)

        db.flush()
        OrderPositionService._apply_totals(order, created)
        AuditService.log_event(
            db,
            entity_type="order",
            entity_id=str(order.id),
            action="copy_lead_estimate",
            user_id=str(acting_user_id) if acting_user_id else None,
            new_value={"lines": len(created), "total": str(order.total_amount)},
        )
        return created


class OrderPaymentService:
    @staticmethod
    def add_payment(
        db: Session,
        order_id: uuid.UUID,
        payload: OrderPaymentCreate,
        acting_user_id: uuid.UUID | None = None,
    ) -> OrderPayment:
        order = OrderPositionService._require_order(db, order_id)
        if payload.method not in PAYMENT_METHODS:
            raise AppError(f"Неизвестный способ оплаты: {payload.method}", 422)

        if payload.method == "deposit":
            from app.modules.clients.deposit import ClientDepositService

            available = ClientDepositService.read(db, order.client_id).balance
            if _round_money(Decimal(payload.amount)) > available:
                raise AppError("Недостаточно денег на депозите клиента", 422)

        payment = OrderPayment(
            order_id=order.id,
            amount=_round_money(Decimal(payload.amount)),
            method=payload.method,
            paid_at=payload.paid_at or datetime.now(UTC),
            comment=payload.comment,
            created_by=acting_user_id,
        )
        db.add(payment)
        db.flush()
        if payload.method == "deposit":
            ClientDepositService.spend(db, order.client_id, order.id, payment.id, payment.amount, acting_user_id)
        AuditService.log_event(
            db,
            entity_type="order",
            entity_id=str(order.id),
            action="add_order_payment",
            user_id=str(acting_user_id) if acting_user_id else None,
            new_value={"amount": str(payment.amount), "method": payment.method},
        )
        db.commit()
        db.refresh(payment)
        return payment

    @staticmethod
    def delete_payment(
        db: Session,
        order_id: uuid.UUID,
        payment_id: uuid.UUID,
        acting_user_id: uuid.UUID | None = None,
    ) -> None:
        payment = db.get(OrderPayment, payment_id)
        if not payment or payment.order_id != order_id:
            raise NotFoundError("Оплата не найдена")
        if payment.method == "deposit":
            from app.modules.clients.deposit import ClientDepositService

            ClientDepositService.return_payment(db, payment.id, acting_user_id)
        AuditService.log_event(
            db,
            entity_type="order",
            entity_id=str(order_id),
            action="delete_order_payment",
            user_id=str(acting_user_id) if acting_user_id else None,
            old_value={"amount": str(payment.amount), "method": payment.method},
        )
        db.delete(payment)
        db.commit()

    @staticmethod
    def to_read(payment: OrderPayment) -> OrderPaymentRead:
        data = OrderPaymentRead.model_validate(payment)
        data.method_label = payment_method_label(payment.method)
        return data

    @staticmethod
    def build_balance(order: Order) -> OrderBalanceRead:
        positions_total = _round_money(sum((item.amount for item in order.positions), Decimal("0")))
        final_amount = round_order_amount(order.final_amount or 0)
        paid = _round_money(sum((item.amount for item in order.payments), Decimal("0")))
        balance = _round_money(paid - final_amount)

        if balance > 0:
            status = "Переплата" if final_amount > 0 else "Аванс"
        elif balance < 0:
            # Ничего не оплачено и смета пустая — это не долг, это пустой заказ.
            status = "Долг" if paid > 0 or final_amount > 0 else "Нет расчёта"
        else:
            status = "Оплачен полностью" if final_amount > 0 else "Нет расчёта"

        by_method: dict[str, Decimal] = {}
        for payment in order.payments:
            by_method[payment.method] = by_method.get(payment.method, Decimal("0")) + Decimal(
                payment.amount
            )

        return OrderBalanceRead(
            positions_total=positions_total,
            final_amount=final_amount,
            paid_amount=paid,
            balance=balance,
            status=status,
            by_method=[
                {
                    "method": method,
                    "label": payment_method_label(method),
                    "amount": str(_round_money(amount)),
                }
                for method, amount in sorted(by_method.items())
            ],
        )
