from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import envelope
from app.db.session import get_db
from app.modules.auth.dependencies import require_permissions
from app.modules.reference_values.schemas import ReferenceValues
from app.modules.reference_values.service import ReferenceValuesService
from app.modules.shared.schemas import Envelope
from app.modules.users.models import User

router = APIRouter()

# Подсказки нужны там, где заполняют таблицу расчёта: приём заявки, смета
# заказа, раскрой. Это накопленные цвета, фрезеровки и артикулы студии — в цехе
# по ним ничего не набирают.
REFERENCE_VALUES_READ = ("leads.manage", "orders.manage", "templates.manage")


@router.get("/reference-values", response_model=Envelope[ReferenceValues])
def reference_values(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*REFERENCE_VALUES_READ))],
) -> dict[str, object]:
    """Цвета и фрезеровки, которые студия уже писала, — для поиска в таблице.

    Справочник плёнок сюда больше не подмешивается: он остаётся справочником
    материалов для раскроя, но подсказку набирает работа студии, а не код.
    """
    return envelope(ReferenceValuesService.collect(db))
