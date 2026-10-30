from __future__ import annotations

import re
import uuid
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError, NotFoundError
from app.modules.audit.service import AuditService
from app.modules.documents.models import Document
from app.modules.documents.schemas import DocumentRead
from app.modules.orders.models import Order, OrderPosition
from app.modules.orders.schemas import PricingComponent
from app.modules.price_book.kinds import unit_label
from app.storage.factory import get_storage_backend

#: Тип файла, который приложил человек. Отличает ручные вложения от выгрузок,
#: которые система кладёт сама («quote», «specification»).
ATTACHMENT_DOC_TYPE = "attachment"

#: Тип содержимого выгрузок. Раньше не проставлялся вовсе, и скачивание отдавало
#: файл под общим `application/octet-stream`, а список файлов печатал «0 КБ».
MARKDOWN_MEDIA_TYPE = "text/markdown; charset=utf-8"

_UNSAFE_NAME = re.compile(r"[^\w.\- ]", re.UNICODE)


def trim_number(value: Decimal) -> str:
    """Число без хвоста нулей: «16.00» → «16», «5.000» → «5».

    Ни `:g`, ни `Decimal.normalize()` тут не годятся: первый оставляет нули как
    есть, второй превращает «100» в «1E+2». В бумагу уходит то, что человек
    писал руками.
    """
    text = f"{value:f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def safe_file_name(name: str) -> str:
    """Имя файла без путей и служебных знаков.

    Клиент присылает «..\\..\\etc\\passwd» и «отчёт*.pdf». Берём только последний
    сегмент и вычищаем всё, кроме букв, цифр, точки, дефиса и пробела, — имя
    уходит и в файловую систему, и в заголовок ответа.
    """
    tail = name.replace("\\", "/").rsplit("/", 1)[-1].strip()
    cleaned = _UNSAFE_NAME.sub("_", tail).strip(" .")
    return cleaned[:180] or "file"


class DocumentService:
    @staticmethod
    def _save_markdown(relative_path: str, lines: list[str]) -> tuple[str, int]:
        """Пишет выгрузку и возвращает путь с размером.

        Байтами, а не текстом: `save_text` на Windows переводит `\n` в `\r\n`,
        и записанный в базу размер разошёлся бы с файлом на диске.
        """
        content = "\n".join(lines).encode("utf-8")
        return get_storage_backend().save_bytes(relative_path, content), len(content)

    @staticmethod
    def _position_line(row: OrderPosition) -> str:
        """Строка спецификации по позиции сметы, как её читают в цехе."""
        title = row.name
        if row.article:
            title = f"арт. {row.article} · {title}"
        size = (
            f"{row.width:.0f}×{row.height:.0f} мм"
            if row.width and row.height
            else "размер не указан"
        )
        parts = [
            f"{row.line_no}. {title}",
            size,
            f"{trim_number(row.quantity)} {unit_label(row.unit)}",
        ]
        if row.thickness:
            parts.append(f"{trim_number(row.thickness)} мм")
        if row.color:
            parts.append(f"цвет: {row.color}")
        if row.milling:
            parts.append(f"фрезеровка: {row.milling}")
        return "- " + ", ".join(parts)

    @staticmethod
    def generate_order_documents(
        db: Session,
        order: Order,
        components: list[PricingComponent],
        acting_user_id: str | None = None,
    ) -> list[Document]:
        """Коммерческое предложение и спецификация по заказу.

        Зовётся из расчёта стоимости. Если описывать нечего — ни строк сметы, ни
        позиций калькулятора, — не создаём ничего: заказчик открывал список файлов
        заказа и видел там две выгрузки из одного заголовка, не понимая, что это.
        """
        order = (
            db.scalar(
                select(Order)
                .options(
                    selectinload(Order.items),
                    selectinload(Order.positions),
                    selectinload(Order.client),
                )
                .where(Order.id == order.id)
            )
            or order
        )
        # Выгрузки всегда описывают текущее состояние заказа, поэтому прошлые
        # снимаем до всего остального. Заодно это чинит дубли: «Рассчитать
        # стоимость» жмут по нескольку раз, и список файлов заполнялся
        # одинаковыми выгрузками.
        db.execute(
            delete(Document).where(
                Document.order_id == order.id,
                Document.doc_type.in_(("quote", "specification")),
            )
        )

        positions = sorted(order.positions, key=lambda row: row.line_no)
        if not positions and not order.items:
            return []

        quote_lines = [
            f"# Коммерческое предложение по заказу {order.order_number}",
            "",
            f"Клиент: {order.client.full_name}",
            f"Валюта: {order.currency}",
        ]
        if order.due_date:
            quote_lines.append(f"Срок: {order.due_date.strftime('%d.%m.%Y')}")
        quote_lines += ["", "## Расчёт"]
        for component in components:
            quote_lines.append(
                f"- {component.name}: {component.quantity} {component.unit} = {component.amount}"
            )
        quote_lines += [
            "",
            f"Итого: {order.total_amount}",
            f"Скидка: {order.discount_amount}",
            f"К оплате: {order.final_amount}",
        ]
        quote_path, quote_size = DocumentService._save_markdown(
            f"documents/{order.id}/quote-{order.order_number}.md", quote_lines
        )

        spec_lines = [f"# Спецификация по заказу {order.order_number}", "", "## Позиции"]
        if positions:
            # Строки сметы — то, что менеджер действительно занёс. Позиции
            # калькулятора (`order.items`) остались от расчёта корпусной мебели и
            # у фасадного заказа почти всегда пусты, поэтому они запасной путь,
            # а не основной: раньше спецификация читала только их и выходила
            # пустой при заполненной смете.
            spec_lines += [DocumentService._position_line(row) for row in positions]
        else:
            spec_lines += [
                f"- {item.name}: {item.width}x{item.height}x{item.depth} мм, "
                f"{item.quantity} шт., тип {item.item_type}"
                for item in order.items
            ]
        spec_path, spec_size = DocumentService._save_markdown(
            f"documents/{order.id}/specification-{order.order_number}.md", spec_lines
        )

        docs = [
            Document(
                order_id=order.id,
                doc_type="quote",
                file_name=f"quote-{order.order_number}.md",
                file_path=quote_path,
                content_type=MARKDOWN_MEDIA_TYPE,
                size_bytes=quote_size,
                created_by=acting_user_id,
            ),
            Document(
                order_id=order.id,
                doc_type="specification",
                file_name=f"specification-{order.order_number}.md",
                file_path=spec_path,
                content_type=MARKDOWN_MEDIA_TYPE,
                size_bytes=spec_size,
                created_by=acting_user_id,
            ),
        ]
        for doc in docs:
            db.add(doc)
        db.flush()
        return docs

    @staticmethod
    def list_order_documents(db: Session, order_id: uuid.UUID) -> list[Document]:
        if not db.get(Order, order_id):
            raise NotFoundError("Заказ не найден")
        return list(
            db.scalars(
                select(Document)
                .options(selectinload(Document.author))
                .where(Document.order_id == order_id)
                .order_by(Document.created_at.desc())
            ).all()
        )

    @staticmethod
    def get_document(db: Session, document_id: uuid.UUID) -> Document:
        document = db.scalar(
            select(Document)
            .options(selectinload(Document.author))
            .where(Document.id == document_id)
        )
        if not document:
            raise NotFoundError("Файл не найден")
        return document

    @staticmethod
    def attach_file(
        db: Session,
        order_id: uuid.UUID,
        *,
        file_name: str,
        content: bytes,
        content_type: str | None,
        comment: str | None,
        max_bytes: int,
        acting_user_id: uuid.UUID | None = None,
    ) -> Document:
        if not db.get(Order, order_id):
            raise NotFoundError("Заказ не найден")
        if not content:
            raise AppError("Файл пустой", 422)
        if len(content) > max_bytes:
            limit_mb = max_bytes // (1024 * 1024)
            raise AppError(f"Файл больше {limit_mb} МБ", 413)

        clean_name = safe_file_name(file_name)
        storage = get_storage_backend()
        # Имя в хранилище своё: два эскиза с именем «фото.jpg» не должны
        # затирать друг друга, а исходное имя показывается в списке.
        stored_path = storage.save_bytes(
            f"documents/{order_id}/attachments/{uuid.uuid4().hex}-{clean_name}",
            content,
        )

        document = Document(
            order_id=order_id,
            doc_type=ATTACHMENT_DOC_TYPE,
            file_name=clean_name,
            file_path=stored_path,
            content_type=content_type,
            size_bytes=len(content),
            comment=comment,
            created_by=acting_user_id,
        )
        db.add(document)
        AuditService.log_event(
            db,
            entity_type="order",
            entity_id=str(order_id),
            action="attach_order_file",
            user_id=str(acting_user_id) if acting_user_id else None,
            new_value={"file_name": clean_name, "size": len(content)},
        )
        db.commit()
        return DocumentService.get_document(db, document.id)

    @staticmethod
    def update_comment(
        db: Session,
        document_id: uuid.UUID,
        comment: str | None,
        acting_user_id: uuid.UUID | None = None,
    ) -> Document:
        document = DocumentService.get_document(db, document_id)
        document.comment = comment
        AuditService.log_event(
            db,
            entity_type="order",
            entity_id=str(document.order_id),
            action="update_order_file_comment",
            user_id=str(acting_user_id) if acting_user_id else None,
            new_value={"file_name": document.file_name},
        )
        db.commit()
        return DocumentService.get_document(db, document_id)

    @staticmethod
    def delete_document(
        db: Session,
        document_id: uuid.UUID,
        acting_user_id: uuid.UUID | None = None,
    ) -> None:
        document = DocumentService.get_document(db, document_id)
        if document.doc_type != ATTACHMENT_DOC_TYPE:
            # Выгрузки удалять нельзя: на них ссылается история заказа, и
            # исчезнувшая карта раскроя выглядит как потерянные данные.
            raise AppError("Системные выгрузки удалять нельзя", 422)

        storage = get_storage_backend()
        try:
            storage.delete(document.file_path)
        except (OSError, ValueError):
            # Файла может уже не быть — переносили хранилище, чистили руками.
            # Запись всё равно надо убрать, иначе список врёт.
            pass

        AuditService.log_event(
            db,
            entity_type="order",
            entity_id=str(document.order_id),
            action="delete_order_file",
            user_id=str(acting_user_id) if acting_user_id else None,
            old_value={"file_name": document.file_name},
        )
        db.delete(document)
        db.commit()

    @staticmethod
    def read_content(document: Document) -> bytes:
        storage = get_storage_backend()
        try:
            return storage.read_bytes(document.file_path)
        except (OSError, ValueError) as exc:
            # Rebase legacy Windows paths only into this order's current storage.
            normalized = str(document.file_path).replace("\\", "/")
            marker = f"documents/{document.order_id}/"
            offset = normalized.find(marker)
            if offset >= 0:
                key = normalized[offset:]
                if all(part not in (".", "..") for part in key.split("/")):
                    try:
                        return storage.read_bytes(key)
                    except (OSError, ValueError):
                        pass
            raise NotFoundError("Файл не найден в хранилище. Проверьте, что папка с файлами перенесена вместе с программой.") from exc

    @staticmethod
    def to_read(document: Document) -> DocumentRead:
        data = DocumentRead.model_validate(document)
        data.author_name = document.author.full_name if document.author else None
        return data
