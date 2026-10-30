from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.db.mixins import UUIDPrimaryKeyMixin, utcnow


class Document(UUIDPrimaryKeyMixin, Base):
    """Файл, привязанный к заказу.

    Два источника: система сама кладёт сюда выгрузки (раскрой, УП для станка) и
    менеджер прикладывает присланное клиентом — эскиз, замер, договор. Заказчик:
    «добавить подгрузку файлов к самому заказу с комментариями, чтобы если что
    клиенту в ответ вот на получай».
    """

    __tablename__ = "documents"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    doc_type: Mapped[str] = mapped_column(String(50))
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    # Тип и размер нужны для отдачи файла назад: без content_type браузер
    # скачает PDF как «неизвестный файл», а без размера в списке не видно,
    # что там лежит на 40 МБ.
    content_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    author: Mapped[User | None] = relationship()
