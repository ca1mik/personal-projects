from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.http import content_disposition
from app.core.responses import envelope
from app.core.xlsx import XLSX_MEDIA_TYPE
from app.db.session import get_db
from app.modules.auth.dependencies import require_permissions
from app.modules.reports.export import (
    build_clients_xlsx,
    build_orders_xlsx,
    build_production_time_xlsx,
    build_volume_xlsx,
    build_work_kind_xlsx,
)
from app.modules.reports.schemas import (
    ClientActivityReport,
    OrderVolumeReport,
    ProductionTimeReport,
    VolumeReport,
    WorkKindReport,
)
from app.modules.reports.service import ReportService
from app.modules.shared.schemas import Envelope
from app.modules.users.models import User

router = APIRouter()

# Отчёты закрыты своим правом, а не правом на сводку.
#
# Раньше здесь стояло dashboard.read, и работник цеха, у которого оно есть ради
# своих этапов и брака, открывал выручку студии, воронку клиентов и выгружал
# клиентскую базу в Excel. Описание его роли при этом обещает обратное:
# «Денег и клиентов не видит».
REPORTS_READ = ("reports.read",)

PeriodQuery = Query(default="month", description="week | month | quarter | year | all")

# Один и тот же параметр во всех отчётах и выгрузках. Заказчик: отбор
# направления доходил только до экрана, а файл считался по всему производству —
# цифры в выгрузке молча расходились с тем, что менеджер только что видел.
DirectionQuery = Query(
    default=None,
    description="Отобрать одно направление: код из справочника или none — заказы без направления",
)

# Галочки в таблице клиентов. Заказчик: «я всех клиентов галочкой выбираю и
# вижу, когда последняя покупка была».
ClientIdsQuery = Query(default=None, description="Отобранные галочками клиенты")

InactiveDaysQuery = Query(
    default=None,
    ge=1,
    description="Оставить только тех, кто не заказывал N дней. Любое число, не только 30/60/90",
)


def _file_suffix(direction_label: str | None) -> str:
    """Хвост имени файла с направлением: по имени видно, что внутри отбор."""
    return f" {direction_label}" if direction_label else ""


def _resolve_client_ids(
    db: Session,
    client_ids: list[uuid.UUID] | None,
    *,
    inactive_days: int | None,
    period: str,
    date_from: date | None,
    date_to: date | None,
    direction_code: str | None,
) -> list[uuid.UUID] | None:
    """Каких клиентов брать в отчёт по заказам.

    Отмеченные галочками — если отметили. Если не отметили, но страница уже
    отобрана порогом «не покупал N дней», берём ровно тех, кто на ней виден.

    Без этого кнопка «Их заказы, Excel» на странице пропавших клиентов молча
    выгружала всю базу заказов: `inactive_days` до этого эндпоинта не доходил,
    и «их» в названии кнопки означало «всех».
    """
    if client_ids:
        return client_ids
    if inactive_days is None:
        return None
    visible = ReportService.client_activity_report(
        db,
        period_code=period,
        date_from=date_from,
        date_to=date_to,
        inactive_days=inactive_days,
        direction_code=direction_code,
    )
    # Пустой список означал бы «отбор не задан» и вернул бы всю базу, поэтому
    # для пустой выборки возвращаем заведомо непустой список из несуществующего
    # идентификатора: в отчёт не попадёт ни один заказ, и это честный ответ.
    return [row.client_id for row in visible.rows] or [uuid.UUID(int=0)]


@router.get("/reports/volume", response_model=Envelope[VolumeReport])
def volume_report(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*REPORTS_READ))],
    metric: str = Query(default="accepted", description="accepted | shipped"),
    period: str = PeriodQuery,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    direction_code: str | None = DirectionQuery,
) -> dict[str, object]:
    """Принято или отгружено за период: в рублях и в м², всего и по направлениям."""
    report = ReportService.volume_report(
        db,
        metric=metric,
        period_code=period,
        date_from=date_from,
        date_to=date_to,
        direction_code=direction_code,
    )
    return envelope(report)


@router.get("/reports/work-kinds", response_model=Envelope[WorkKindReport])
def work_kind_report(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*REPORTS_READ))],
    metric: str = Query(default="accepted", description="accepted | shipped"),
    period: str = PeriodQuery,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    direction_code: str | None = DirectionQuery,
) -> dict[str, object]:
    """Обработка за период: фрезеровка, шпон, мыло — в м², штуках и рублях."""
    report = ReportService.work_kind_report(
        db,
        metric=metric,
        period_code=period,
        date_from=date_from,
        date_to=date_to,
        direction_code=direction_code,
    )
    return envelope(report)


@router.get("/reports/clients", response_model=Envelope[ClientActivityReport])
def client_activity_report(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*REPORTS_READ))],
    period: str = Query(default="all", description="week | month | quarter | year | all"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    inactive_days: int | None = InactiveDaysQuery,
    direction_code: str | None = DirectionQuery,
    client_ids: list[uuid.UUID] | None = ClientIdsQuery,
) -> dict[str, object]:
    """Сумма покупок за период и кто давно не покупал."""
    report = ReportService.client_activity_report(
        db,
        period_code=period,
        date_from=date_from,
        date_to=date_to,
        inactive_days=inactive_days,
        direction_code=direction_code,
        client_ids=client_ids,
    )
    return envelope(report)


@router.get("/reports/orders", response_model=Envelope[OrderVolumeReport])
def order_volume_report(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*REPORTS_READ))],
    metric: str = Query(default="accepted", description="accepted | shipped"),
    period: str = PeriodQuery,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    direction_code: str | None = DirectionQuery,
    inactive_days: int | None = InactiveDaysQuery,
    client_ids: list[uuid.UUID] | None = ClientIdsQuery,
) -> dict[str, object]:
    """Заказы построчно: строка = заказ с суммой и площадью."""
    report = ReportService.order_volume_report(
        db,
        metric=metric,
        period_code=period,
        date_from=date_from,
        date_to=date_to,
        direction_code=direction_code,
        client_ids=_resolve_client_ids(
            db,
            client_ids,
            inactive_days=inactive_days,
            period=period,
            date_from=date_from,
            date_to=date_to,
            direction_code=direction_code,
        ),
    )
    return envelope(report)


@router.get("/reports/production-time", response_model=Envelope[ProductionTimeReport])
def production_time_report(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions("production.read"))],
    period: str = PeriodQuery,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    direction_code: str | None = DirectionQuery,
) -> dict[str, object]:
    """Сколько времени занимает каждый этап и сколько идёт заказ целиком."""
    report = ReportService.production_time_report(
        db,
        period_code=period,
        date_from=date_from,
        date_to=date_to,
        direction_code=direction_code,
    )
    return envelope(report)


def _xlsx(content: bytes, file_name: str) -> Response:
    """Одинаковая отдача файла: имя по-русски уезжает по RFC 5987."""
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": content_disposition(file_name)},
    )


@router.get("/reports/volume.xlsx")
def volume_report_xlsx(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*REPORTS_READ))],
    metric: str = Query(default="accepted", description="accepted | shipped"),
    period: str = PeriodQuery,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    direction_code: str | None = DirectionQuery,
) -> Response:
    report = ReportService.volume_report(
        db,
        metric=metric,
        period_code=period,
        date_from=date_from,
        date_to=date_to,
        direction_code=direction_code,
    )
    return _xlsx(
        build_volume_xlsx(report),
        f"Объёмы {report.metric_label} {report.period.label}"
        f"{_file_suffix(report.direction_label)}.xlsx",
    )


@router.get("/reports/work-kinds.xlsx")
def work_kind_report_xlsx(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*REPORTS_READ))],
    metric: str = Query(default="accepted", description="accepted | shipped"),
    period: str = PeriodQuery,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    direction_code: str | None = DirectionQuery,
) -> Response:
    report = ReportService.work_kind_report(
        db,
        metric=metric,
        period_code=period,
        date_from=date_from,
        date_to=date_to,
        direction_code=direction_code,
    )
    return _xlsx(
        build_work_kind_xlsx(report),
        f"Обработка {report.metric_label} {report.period.label}"
        f"{_file_suffix(report.direction_label)}.xlsx",
    )


@router.get("/reports/clients.xlsx")
def client_activity_report_xlsx(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*REPORTS_READ))],
    period: str = Query(default="all"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    inactive_days: int | None = InactiveDaysQuery,
    direction_code: str | None = DirectionQuery,
    client_ids: list[uuid.UUID] | None = ClientIdsQuery,
) -> Response:
    report = ReportService.client_activity_report(
        db,
        period_code=period,
        date_from=date_from,
        date_to=date_to,
        inactive_days=inactive_days,
        direction_code=direction_code,
        client_ids=client_ids,
    )
    # Второй лист — заказы ровно тех клиентов, что попали в сводку: иначе
    # «Заказы» в файле шире таблицы над ними, и сумма листов не сходится.
    orders = ReportService.order_volume_report(
        db,
        metric="accepted",
        period_code=period,
        date_from=date_from,
        date_to=date_to,
        direction_code=direction_code,
        client_ids=[row.client_id for row in report.rows],
    )
    return _xlsx(
        build_clients_xlsx(report, orders),
        f"Клиенты {report.period.label}{_file_suffix(report.direction_label)}.xlsx",
    )


@router.get("/reports/orders.xlsx")
def order_volume_report_xlsx(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions(*REPORTS_READ))],
    metric: str = Query(default="accepted", description="accepted | shipped"),
    period: str = PeriodQuery,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    direction_code: str | None = DirectionQuery,
    inactive_days: int | None = InactiveDaysQuery,
    client_ids: list[uuid.UUID] | None = ClientIdsQuery,
) -> Response:
    report = ReportService.order_volume_report(
        db,
        metric=metric,
        period_code=period,
        date_from=date_from,
        date_to=date_to,
        direction_code=direction_code,
        client_ids=_resolve_client_ids(
            db,
            client_ids,
            inactive_days=inactive_days,
            period=period,
            date_from=date_from,
            date_to=date_to,
            direction_code=direction_code,
        ),
    )
    return _xlsx(
        build_orders_xlsx(report),
        f"Заказы {report.metric_label} {report.period.label}"
        f"{_file_suffix(report.direction_label)}.xlsx",
    )


@router.get("/reports/production-time.xlsx")
def production_time_report_xlsx(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permissions("production.read"))],
    period: str = PeriodQuery,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    direction_code: str | None = DirectionQuery,
) -> Response:
    report = ReportService.production_time_report(
        db,
        period_code=period,
        date_from=date_from,
        date_to=date_to,
        direction_code=direction_code,
    )
    return _xlsx(
        build_production_time_xlsx(report),
        f"Время изготовления {report.period.label}" f"{_file_suffix(report.direction_label)}.xlsx",
    )
