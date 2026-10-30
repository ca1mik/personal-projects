from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.material_text import clean_color
from app.modules.leads.models import Lead
from app.modules.orders.models import OrderPosition
from app.modules.reference_values.schemas import ReferenceValue, ReferenceValues
from app.modules.templates.film_cutting import FILM_COLORS

#: Сколько заявок просматриваем ради подсказок. Полный перебор здесь не нужен:
#: цвета студии повторяются, а свежие важнее — их менеджер и ищет.
LEADS_SCAN_LIMIT = 500

#: Цвета из зашитого в код справочника плёнок.
#:
#: Их убрали из подсказок напрямую, но они возвращались кругом: новой детали
#: раскрой подставляет первый материал списка — «Белый глянец», — и при
#: сохранении раскроя заявкой это имя уезжает в `raw_payload.parts[].material`,
#: откуда подсказки его и читают. Через одну сохранённую заявку список снова
#: наполнялся тем, на что жаловался заказчик: «все эти цвета, какие-то
#: непонятные, откуда-то там взявшиеся».
#:
#: Поэтому имена справочника в подсказки не берём вовсе. Живой цвет студии
#: пишется руками и с зашитыми названиями не совпадает.
_SEEDED_COLOR_NAMES = frozenset(
    (clean_color(color.name) or color.name).casefold() for color in FILM_COLORS
)

#: Сколько вариантов отдаём в каждом списке. Больше в выпадающий список всё
#: равно не влезет, а поиск на фронте работает по всему присланному.
MAX_VALUES = 200


def _clean(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _clean_color_value(value: object) -> str:
    """Цвет для подсказки — только цвет.

    В базе накоплены записи вида «Эмаль RAL 9003 плита 19мм», и подсказка
    предлагала именно их: менеджер выбирал из списка и снова заносил в цвет
    толщину с видом работ. Сводим к одному правилу вместе со счётчиком — все
    написания одного цвета складываются в одну строку списка.
    """
    cleaned = clean_color(value) or ""
    # Зашитый в код цвет — не то, что писала студия. См. _SEEDED_COLOR_NAMES.
    if cleaned.casefold() in _SEEDED_COLOR_NAMES:
        return ""
    return cleaned


class ReferenceValuesService:
    """Подсказки для полей «Цвет» и «Фрезеровка».

    Заказчик: «надо по поиску сделать поиск из базы уже созданной». Настоящие
    значения студии («Эмаль RAL 9003 плита 19мм», «фрез рамка под стекло») в
    справочниках не заведены — они копятся в заявках и заказах. Поэтому список
    собираем из того, что уже писали руками, и сортируем по частоте: чем чаще
    значение встречалось, тем выше оно в подсказке.
    """

    @staticmethod
    def _from_leads(db: Session) -> tuple[Counter[str], Counter[str], Counter[str]]:
        colors: Counter[str] = Counter()
        millings: Counter[str] = Counter()
        articles: Counter[str] = Counter()

        leads = db.scalars(
            select(Lead).order_by(Lead.created_at.desc()).limit(LEADS_SCAN_LIMIT)
        ).all()
        for lead in leads:
            payload = lead.parsed_payload_json or {}
            raw = payload.get("raw_payload") or {}
            parts = raw.get("parts")
            if not isinstance(parts, list):
                continue
            for part in parts:
                if not isinstance(part, dict):
                    continue
                color = _clean_color_value(part.get("material"))
                if color:
                    colors[color] += 1
                milling = _clean(part.get("milling"))
                if milling:
                    millings[milling] += 1
                article = _clean(part.get("article"))
                if article:
                    articles[article] += 1
        return colors, millings, articles

    @staticmethod
    def _from_orders(db: Session) -> tuple[Counter[str], Counter[str], Counter[str]]:
        colors: Counter[str] = Counter()
        millings: Counter[str] = Counter()
        articles: Counter[str] = Counter()
        rows = db.execute(
            select(OrderPosition.color, OrderPosition.milling, OrderPosition.article)
        ).all()
        for color, milling, article in rows:
            cleaned_color = _clean_color_value(color)
            if cleaned_color:
                colors[cleaned_color] += 1
            if _clean(milling):
                millings[_clean(milling)] += 1
            if _clean(article):
                articles[_clean(article)] += 1
        return colors, millings, articles

    @staticmethod
    def collect(db: Session) -> ReferenceValues:
        """Только то, что студия писала сама.

        Раньше в подсказку подмешивались два посторонних источника: цвета из
        зашитого в код справочника плёнок и названия артикулов типа
        «Фрезеровка». Заказчик на это и пожаловался: «все эти артикула, все
        цвета, какие-то непонятные, откуда-то там взявшиеся». В списке рядом с
        живыми «фрез» и «мыло» висели «Кашемир матовый», которым никто ни разу
        не пользовался, и целиком название артикула — «Фрезерованный фасад,
        арт. 116, эмаль».

        Теперь подсказка пустая, пока не занесли первую заявку, и дальше растёт
        сама: «постепенно программа наберёт всё, что у нас есть в ассортименте».

        Номера артикулов копятся тем же способом. Заказчик: «я первый раз
        заполняю заявку и вручную прописываю артикул, например 128 — и этот
        артикул программа должна сохранить, а потом уже можно будет из списка
        его выбирать». Раньше артикул предлагался только из справочника цен, а
        туда он попадал лишь при создании заказа: набрала номер в заявке, вышла,
        вернулась — номера нет.
        """
        lead_colors, lead_millings, lead_articles = ReferenceValuesService._from_leads(db)
        order_colors, order_millings, order_articles = ReferenceValuesService._from_orders(db)

        colors = lead_colors + order_colors
        millings = lead_millings + order_millings
        articles = lead_articles + order_articles

        return ReferenceValues(
            colors=ReferenceValuesService._to_values(colors),
            millings=ReferenceValuesService._to_values(millings),
            articles=ReferenceValuesService._to_values(articles),
        )

    @staticmethod
    def _to_values(counter: Counter[str]) -> list[ReferenceValue]:
        """Сначала то, что писали чаще, при равенстве — по алфавиту."""
        items = [(value, count) for value, count in counter.items() if value]
        items.sort(key=lambda pair: (-pair[1], pair[0].casefold()))
        return [ReferenceValue(value=value, used=count) for value, count in items[:MAX_VALUES]]
