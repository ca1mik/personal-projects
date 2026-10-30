from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.http import content_disposition
from app.core.responses import envelope
from app.db.session import get_db
from app.modules.auth.dependencies import require_permissions
from app.modules.documents.schemas import DocumentRead, DocumentUpdate
from app.modules.documents.service import DocumentService
from app.modules.shared.schemas import Envelope, MessageEnvelope
from app.modules.users.models import User

router = APIRouter(tags=["documents"])

DEFAULT_MEDIA_TYPE = "application/octet-stream"

# Файлы заказа — это эскизы и замеры, по которым работает цех, поэтому смотреть
# и скачивать их может и производство.
DOCUMENTS_READ = ("orders.manage", "production.read", "production.manage")
# Прикладывать и переподписывать файлы — те, кто отвечает за заказ и за запуск.
DOCUMENTS_WRITE = ("orders.manage", "production.manage")
# Удаление файла невосстановимо: скан договора или замер вернуть будет неоткуда.
DOCUMENTS_DELETE = ("orders.manage",)


@router.get("/orders/{order_id}/files", response_model=Envelope[list[DocumentRead]])
def list_order_files(
    order_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*DOCUMENTS_READ))],
) -> dict[str, object]:
    """Все файлы заказа: и приложенные руками, и выгрузки системы."""
    documents = DocumentService.list_order_documents(db, order_id)
    return envelope([DocumentService.to_read(item) for item in documents])


@router.post("/orders/{order_id}/files", response_model=Envelope[DocumentRead])
async def upload_order_file(
    order_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*DOCUMENTS_WRITE))],
    file: Annotated[UploadFile, File()],
    comment: Annotated[str | None, Form()] = None,
) -> dict[str, object]:
    """Приложить файл к заказу: эскиз, замер, скан договора."""
    settings = get_settings()
    content = await file.read()
    document = DocumentService.attach_file(
        db,
        order_id,
        file_name=file.filename or "file",
        content=content,
        content_type=file.content_type,
        comment=(comment or None),
        max_bytes=settings.order_file_max_mb * 1024 * 1024,
        acting_user_id=current_user.id,
    )
    return envelope(DocumentService.to_read(document))


@router.get("/documents/{document_id}/download")
def download_document(
    document_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*DOCUMENTS_READ))],
) -> Response:
    document = DocumentService.get_document(db, document_id)
    content = DocumentService.read_content(document)
    return Response(
        content=content,
        media_type=document.content_type or DEFAULT_MEDIA_TYPE,
        headers={"Content-Disposition": content_disposition(document.file_name)},
    )


@router.patch("/documents/{document_id}", response_model=Envelope[DocumentRead])
def update_document(
    document_id: uuid.UUID,
    payload: DocumentUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*DOCUMENTS_WRITE))],
) -> dict[str, object]:
    document = DocumentService.update_comment(db, document_id, payload.comment, current_user.id)
    return envelope(DocumentService.to_read(document))


@router.delete("/documents/{document_id}", response_model=MessageEnvelope)
def delete_document(
    document_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions(*DOCUMENTS_DELETE))],
) -> dict[str, object]:
    DocumentService.delete_document(db, document_id, current_user.id)
    return {"data": {"message": "Файл удалён"}}
