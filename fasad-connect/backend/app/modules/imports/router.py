from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.exceptions import AppError
from app.core.responses import envelope
from app.modules.auth.dependencies import require_permissions
from app.modules.imports.parser import ParseResult, PartsImportError, parse_parts_file
from app.modules.imports.schemas import ImportedPartRead, PartsImportRead
from app.modules.shared.schemas import Envelope
from app.modules.users.models import User

router = APIRouter()

# Бланк заказа — это несколько десятков строк, мегабайты здесь не нужны.
# Ограничение заодно защищает от загрузки чего-то постороннего.
MAX_IMPORT_BYTES = 5 * 1024 * 1024

# Разбор бланка — первый шаг приёма заявки или оформления заказа. В файле лежат
# размеры и фамилия заказчика, поэтому в цех этот эндпоинт не отдаём.
IMPORTS_PARSE = ("leads.manage", "orders.manage")


def _to_read(file_name: str, result: ParseResult) -> PartsImportRead:
    return PartsImportRead(
        file_name=file_name,
        sheet_name=result.sheet_name,
        customer=result.customer,
        order_number=result.order_number,
        # сборка через from_parsed: новые поля разбора доезжают до ответа сами
        parts=[ImportedPartRead.from_parsed(part) for part in result.parts],
        total_quantity=result.total_quantity,
        total_area_sqm=result.total_area_sqm,
        # тот же формат, что менеджер набирает руками в поле «Размеры списком»
        size_lines="\n".join(
            f"{part.width} {part.height} {part.quantity}" for part in result.parts
        ),
    )


@router.post("/imports/parts", response_model=Envelope[PartsImportRead])
async def import_parts(
    _: Annotated[User, Depends(require_permissions(*IMPORTS_PARSE))],
    file: Annotated[UploadFile, File(...)],
) -> dict[str, object]:
    """Разбирает выгрузку заказчика и возвращает список деталей.

    Ничего не сохраняет: менеджер сначала видит, что разобралось, и только
    потом решает, создавать ли из этого заявку.
    """
    content = await file.read()
    if len(content) > MAX_IMPORT_BYTES:
        raise AppError("Файл больше 5 МБ. Пришлите только лист с размерами.", status_code=413)

    try:
        result = parse_parts_file(file.filename or "", content)
    except PartsImportError as error:
        # ошибки разбора отдаём в том же виде, что и остальной API
        raise AppError(str(error), status_code=422) from error

    return envelope(_to_read(file.filename or "", result))
