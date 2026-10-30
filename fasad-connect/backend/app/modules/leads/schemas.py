from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.clients.schemas import ClientRead
from app.modules.directions.schemas import DirectionSummaryRead
from app.modules.leads.statuses import LEAD_STATUSES
from app.modules.shared.schemas import ORMModel
from app.modules.users.schemas import UserRead

__all__ = ["LEAD_STATUSES"]

#: Статусы заявки, которые можно поставить руками.
#:
#: Список закрытый и общий с карточкой клиента: см. `leads/statuses.py`. Пока
#: списков было два, правка заявки разрешала «Квалифицирована», а карточка
#: клиента такого кода не знала и печатала в плашку сырое `qualified`.


class LeadAttachmentRead(ORMModel):
    id: uuid.UUID
    file_name: str
    file_path: str
    mime_type: str | None
    size_bytes: int


class LeadOrderRef(BaseModel):
    """Заказ, выросший из заявки: номер и то, чем на него сослаться.

    Заказчик видел в карточке заявки только «заказов: 1» и не мог в этот заказ
    перейти — приходилось искать его в списке по номеру, которого он ещё не
    знал.
    """

    id: uuid.UUID
    order_number: str
    final_amount: Decimal = Decimal("0")
    currency: str = "RUB"
    #: Экранный бланк заявки показывает его вместо замороженного raw_text
    #: заявки, когда заказ уже создан (см. leads/router.py::download_lead_blank).
    comment: str | None = None


class LeadSummaryRead(BaseModel):
    """Сводка заявки: то, что менеджер должен увидеть сразу после её создания.

    Площадь считается по разобранным размерам, поэтому она есть у любой заявки.
    ``estimated_amount`` появляется, только если расчёт действительно был
    (заявка из справочника или из бота) — сумму «на глазок» здесь не выдумываем.
    ``orders_amount`` — уже фактические деньги по созданным заказам.
    """

    quantity: int = 1
    facade_area_sqm: Decimal = Decimal("0")
    material_area_sqm: Decimal = Decimal("0")
    estimated_amount: Decimal | None = None
    orders_count: int = 0
    orders_amount: Decimal = Decimal("0")
    currency: str = "RUB"
    #: Сами заказы, а не только их число: по ним карточка заявки даёт ссылку.
    orders: list[LeadOrderRef] = []


class LeadRead(ORMModel):
    deleted_at: datetime | None = None
    id: uuid.UUID
    lead_number: str | None = None
    source_channel: str
    external_message_id: str | None
    subject: str | None
    raw_text: str
    normalized_text: str | None
    parsed_payload_json: dict[str, Any]
    status: str
    # Срок, названный клиенту: подставлен типовым по типу работ или задан руками.
    due_date: date | None = None
    direction_id: uuid.UUID | None = None
    client_id: uuid.UUID | None
    assigned_manager_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    client: ClientRead | None = None
    direction: DirectionSummaryRead | None = None
    assigned_manager: UserRead | None = None
    attachments: list[LeadAttachmentRead] = []
    summary: LeadSummaryRead | None = None


class LeadUpdate(BaseModel):
    """Правка сохранённой заявки.

    Заказчик: сохранённую заявку нельзя было исправить вообще. Клиент отказался —
    заявка навсегда оставалась «новой» и висела в карточке клиента как «ждёт
    ответа»; ошиблись в номере или в сроке — переписать было нечем.
    """

    direction_id: uuid.UUID | None = None
    direction_code: str | None = None
    status: str | None = None
    assigned_manager_id: uuid.UUID | None = None
    # Срок правится и после приёма: клиент попросил раньше или согласился ждать.
    due_date: date | None = None
    # Номер заявки правится и после создания: студия переносит свою нумерацию в
    # систему задним числом, а раньше номер писался ровно один раз при приёме.
    lead_number: str | None = Field(default=None, max_length=20)
    # Адрес доставки этой заявки. Хранится при заявке, а не в карточке клиента:
    # см. ``LeadService._store_lead_address``.
    address: str | None = Field(default=None, max_length=500)
    part_articles: list[str | None] | None = Field(default=None, max_length=200)

    @field_validator("part_articles")
    @classmethod
    def _valid_part_articles(cls, value: list[str | None] | None) -> list[str | None] | None:
        if value is None:
            return None
        articles = [(article or "").strip() or None for article in value]
        if any(article is not None and len(article) > 50 for article in articles):
            raise ValueError("Артикул не может быть длиннее 50 символов")
        return articles

    @field_validator("status")
    @classmethod
    def _known_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        code = value.strip()
        if code not in LEAD_STATUSES:
            # Сообщение по-русски и с самим значением: его читает менеджер.
            raise ValueError(f"Неизвестный статус заявки: «{value}»")
        return code


class LeadFilterParams(BaseModel):
    status: str | None = None
    source_channel: str | None = None
    direction_code: str | None = None
    search: str | None = None


class LeadCreateOrderRequest(BaseModel):
    manager_id: uuid.UUID | None = None
    # Свой номер заказа. Пусто — система ставит сама сквозной нумерацией.
    order_number: str | None = Field(default=None, max_length=50)


class LeadNormalizedPayload(BaseModel):
    client_name: str | None = None
    # Клиент, выбранный менеджером из базы: имеет приоритет над поиском по контактам.
    client_id: uuid.UUID | None = None
    phone: str | None = None
    email: str | None = None
    # Адрес доставки или объекта. Заказчик: «адрес клиента не вижу куда вбивать» —
    # поле в карточке клиента было, а занести его при приёме заявки было негде.
    address: str | None = None
    # Организация клиента — то же самое, что и с адресом: поле на «Рабочем
    # месте» есть, но раньше уходило только текстом внутрь заявки, а не в
    # карточку клиента.
    organization: str | None = None
    text: str | None = None
    dimensions: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")
