"""Пункты 4, 5, 6 ТЗ: отчёты по клиентам, по принятым и отгруженным объёмам.

Цифры в фикстурах подобраны так, чтобы площадь считалась в уме:
фасад 1000×500 мм = 0,5 м². Поэтому любое расхождение видно сразу.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.modules.directions.models import ProductionDirection
from app.modules.orders.models import Order
from app.modules.reports.periods import month_label, resolve_period

# 1000 × 500 мм = 0.5 м² за штуку
FACADE = {"item_type": "facade", "name": "Фасад", "width": "1000", "height": "500", "depth": "16"}


@pytest.fixture
def directions(db_session):
    """Эмаль — коэффициент 1, ПВХ — 2 (плёнка на две стороны), шпон — 1."""
    rows = [
        ("enamel", "Эмаль", "", Decimal("1.000"), 10),
        ("pvc", "ПВХ", "П", Decimal("2.000"), 20),
        ("veneer", "Шпон", "Ш", Decimal("1.000"), 30),
    ]
    for code, name, suffix, factor, sort_order in rows:
        db_session.add(
            ProductionDirection(
                code=code,
                name=name,
                number_suffix=suffix,
                material_area_factor=factor,
                sort_order=sort_order,
                is_active=True,
            )
        )
    db_session.commit()


def make_client(client, auth_headers, name="Иван Петров", organization="ООО «Мебель»"):
    response = client.post(
        "/api/v1/clients",
        headers=auth_headers,
        json={"full_name": name, "organization": organization, "phone": "+79990001122"},
    )
    return response.json()["data"]["id"]


def manager_id(client, auth_headers):
    return client.get("/api/v1/admin/users?page=1&size=5", headers=auth_headers).json()["data"][0][
        "id"
    ]


def make_order(
    client,
    auth_headers,
    client_id,
    manager,
    direction_code,
    quantity,
    amount=None,
    db_session=None,
):
    """Заказ с одной позицией. ``amount`` требует ``db_session``.

    Сумму ставим напрямую в базу: обычно она приходит из расчёта, а здесь
    проверяется именно агрегация отчёта, а не прайсинг.
    """
    payload = {"client_id": client_id, "manager_id": manager}
    if direction_code:
        payload["direction_code"] = direction_code
    order = client.post("/api/v1/orders", headers=auth_headers, json=payload).json()["data"]
    client.post(
        f"/api/v1/orders/{order['id']}/items",
        headers=auth_headers,
        json={**FACADE, "quantity": quantity},
    )
    if amount is not None:
        if db_session is None:
            raise AssertionError("для указания суммы передайте db_session")
        set_amount(db_session, order["id"], amount)
    return order


def set_amount(db_session, order_id: str, amount) -> None:
    stored = db_session.get(Order, uuid.UUID(order_id))
    stored.final_amount = Decimal(str(amount))
    db_session.commit()


def shift_created_at(db_session, order_id: str, days: int) -> None:
    stored = db_session.get(Order, uuid.UUID(order_id))
    stored.created_at = datetime.now(UTC) - timedelta(days=days)
    db_session.commit()


# --- площадь ---------------------------------------------------------------


def test_facade_and_material_area_differ_for_pvc(client, auth_headers, directions):
    client_id = make_client(client, auth_headers)
    manager = manager_id(client, auth_headers)
    # 4 фасада по 0.5 м² = 2 м² фасада; ПВХ на две стороны = 4 м² плёнки
    make_order(client, auth_headers, client_id, manager, "pvc", quantity=4)

    report = client.get(
        "/api/v1/reports/volume?metric=accepted&period=all", headers=auth_headers
    ).json()["data"]

    assert Decimal(report["total"]["facade_area_sqm"]) == Decimal("2.000")
    assert Decimal(report["total"]["material_area_sqm"]) == Decimal("4.000")


def test_enamel_material_area_equals_facade_area(client, auth_headers, directions):
    client_id = make_client(client, auth_headers)
    manager = manager_id(client, auth_headers)
    make_order(client, auth_headers, client_id, manager, "enamel", quantity=6)

    report = client.get("/api/v1/reports/volume?period=all", headers=auth_headers).json()["data"]

    assert Decimal(report["total"]["facade_area_sqm"]) == Decimal("3.000")
    assert Decimal(report["total"]["material_area_sqm"]) == Decimal("3.000")


# --- отчёт по объёмам (пп. 5, 6) ------------------------------------------


def test_volume_report_splits_by_direction(client, auth_headers, directions, db_session):
    client_id = make_client(client, auth_headers)
    manager = manager_id(client, auth_headers)
    make_order(
        client,
        auth_headers,
        client_id,
        manager,
        "enamel",
        quantity=2,
        amount=10000,
        db_session=db_session,
    )
    make_order(
        client,
        auth_headers,
        client_id,
        manager,
        "pvc",
        quantity=4,
        amount=20000,
        db_session=db_session,
    )
    make_order(
        client,
        auth_headers,
        client_id,
        manager,
        "veneer",
        quantity=2,
        amount=30000,
        db_session=db_session,
    )

    report = client.get("/api/v1/reports/volume?period=all", headers=auth_headers).json()["data"]

    assert report["metric_label"] == "Принято"
    assert report["total"]["orders_count"] == 3
    assert Decimal(report["total"]["amount"]) == Decimal("60000")
    # 1 + 2 + 1 = 4 м² фасадов; материала 1 + 4 + 1 = 6 м²
    assert Decimal(report["total"]["facade_area_sqm"]) == Decimal("4.000")
    assert Decimal(report["total"]["material_area_sqm"]) == Decimal("6.000")

    by_direction = {row["label"]: row for row in report["by_direction"]}
    assert set(by_direction) == {"Эмаль", "ПВХ", "Шпон"}
    assert Decimal(by_direction["Шпон"]["amount"]) == Decimal("30000")
    assert Decimal(by_direction["ПВХ"]["material_area_sqm"]) == Decimal("4.000")
    # Направления отсортированы по деньгам — сверху самое дорогое
    assert report["by_direction"][0]["label"] == "Шпон"


def test_volume_report_orders_without_direction_are_grouped(client, auth_headers, directions):
    client_id = make_client(client, auth_headers)
    manager = manager_id(client, auth_headers)
    order = client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={"client_id": client_id, "manager_id": manager},
    ).json()["data"]
    client.post(
        f"/api/v1/orders/{order['id']}/items",
        headers=auth_headers,
        json={**FACADE, "quantity": 2},
    )

    report = client.get("/api/v1/reports/volume?period=all", headers=auth_headers).json()["data"]

    labels = [row["label"] for row in report["by_direction"]]
    assert "Без направления" in labels


def test_shipped_report_counts_only_shipped_orders(client, auth_headers, directions, db_session):
    client_id = make_client(client, auth_headers)
    manager = manager_id(client, auth_headers)
    shipped = make_order(
        client,
        auth_headers,
        client_id,
        manager,
        "pvc",
        quantity=2,
        amount=5000,
        db_session=db_session,
    )
    make_order(
        client,
        auth_headers,
        client_id,
        manager,
        "enamel",
        quantity=2,
        amount=7000,
        db_session=db_session,
    )

    stored = db_session.get(Order, uuid.UUID(shipped["id"]))
    stored.shipped_at = datetime.now(UTC)
    db_session.commit()

    accepted = client.get("/api/v1/reports/volume?period=all", headers=auth_headers).json()["data"]
    report = client.get(
        "/api/v1/reports/volume?metric=shipped&period=all", headers=auth_headers
    ).json()["data"]

    assert accepted["total"]["orders_count"] == 2
    assert report["metric_label"] == "Отгружено"
    assert report["total"]["orders_count"] == 1
    assert Decimal(report["total"]["amount"]) == Decimal("5000")


def test_volume_report_respects_explicit_dates(client, auth_headers, directions, db_session):
    client_id = make_client(client, auth_headers)
    manager = manager_id(client, auth_headers)
    old = make_order(
        client,
        auth_headers,
        client_id,
        manager,
        "enamel",
        quantity=2,
        amount=1000,
        db_session=db_session,
    )
    make_order(
        client,
        auth_headers,
        client_id,
        manager,
        "pvc",
        quantity=2,
        amount=2000,
        db_session=db_session,
    )

    shift_created_at(db_session, old["id"], days=400)

    everything = client.get("/api/v1/reports/volume?period=all", headers=auth_headers).json()[
        "data"
    ]
    this_year = client.get("/api/v1/reports/volume?period=year", headers=auth_headers).json()[
        "data"
    ]

    assert everything["total"]["orders_count"] == 2
    assert this_year["total"]["orders_count"] == 1
    assert Decimal(this_year["total"]["amount"]) == Decimal("2000")


def test_empty_period_returns_zeros(client, auth_headers, directions):
    report = client.get(
        "/api/v1/reports/volume?date_from=2020-01-01&date_to=2020-12-31", headers=auth_headers
    ).json()["data"]

    assert report["total"]["orders_count"] == 0
    assert Decimal(report["total"]["amount"]) == Decimal("0")
    assert report["by_direction"] == []


# --- отчёт по клиентам (п. 4) ---------------------------------------------


def test_client_report_marks_regular_and_new(client, auth_headers, directions, db_session):
    manager = manager_id(client, auth_headers)
    regular = make_client(client, auth_headers, "Постоянный Клиент", "ООО «Постоянство»")
    newcomer = make_client(client, auth_headers, "Новый Клиент", None)

    for _ in range(3):
        make_order(
            client,
            auth_headers,
            regular,
            manager,
            "pvc",
            quantity=2,
            amount=10000,
            db_session=db_session,
        )
    make_order(
        client,
        auth_headers,
        newcomer,
        manager,
        "enamel",
        quantity=2,
        amount=4000,
        db_session=db_session,
    )

    rows = client.get("/api/v1/reports/clients?period=all", headers=auth_headers).json()["data"][
        "rows"
    ]
    by_name = {row["full_name"]: row for row in rows}

    assert by_name["Постоянный Клиент"]["category_label"] == "Постоянный"
    assert by_name["Постоянный Клиент"]["orders_count"] == 3
    assert Decimal(by_name["Постоянный Клиент"]["amount"]) == Decimal("30000")
    assert by_name["Постоянный Клиент"]["directions"] == ["ПВХ"]
    assert by_name["Новый Клиент"]["category_label"] == "Новый"


def test_client_report_filters_who_has_not_bought_for_long(
    client, auth_headers, directions, db_session
):
    manager = manager_id(client, auth_headers)
    stale = make_client(client, auth_headers, "Спящий Клиент", "ООО «Тишина»")
    fresh = make_client(client, auth_headers, "Свежий Клиент", "ООО «Активность»")

    old_order = make_order(
        client,
        auth_headers,
        stale,
        manager,
        "veneer",
        quantity=2,
        amount=8000,
        db_session=db_session,
    )
    make_order(
        client,
        auth_headers,
        fresh,
        manager,
        "enamel",
        quantity=2,
        amount=9000,
        db_session=db_session,
    )

    shift_created_at(db_session, old_order["id"], days=200)

    report = client.get(
        "/api/v1/reports/clients?period=all&inactive_days=120", headers=auth_headers
    ).json()["data"]

    names = [row["full_name"] for row in report["rows"]]
    assert names == ["Спящий Клиент"]
    assert report["rows"][0]["category_label"] == "Потерянный"
    assert report["rows"][0]["days_since_last_order"] >= 200


def test_client_report_filters_by_direction(client, auth_headers, directions, db_session):
    manager = manager_id(client, auth_headers)
    pvc_client = make_client(client, auth_headers, "Клиент ПВХ", None)
    enamel_client = make_client(client, auth_headers, "Клиент Эмаль", None)
    make_order(
        client,
        auth_headers,
        pvc_client,
        manager,
        "pvc",
        quantity=2,
        amount=1000,
        db_session=db_session,
    )
    make_order(
        client,
        auth_headers,
        enamel_client,
        manager,
        "enamel",
        quantity=2,
        amount=2000,
        db_session=db_session,
    )

    report = client.get(
        "/api/v1/reports/clients?period=all&direction_code=pvc", headers=auth_headers
    ).json()["data"]

    paying = [row for row in report["rows"] if row["orders_count"] > 0]
    assert [row["full_name"] for row in paying] == ["Клиент ПВХ"]
    assert Decimal(report["total"]["amount"]) == Decimal("1000")


def test_client_without_orders_is_listed_as_no_orders(client, auth_headers, directions):
    make_client(client, auth_headers, "Только Заведён", None)

    rows = client.get("/api/v1/reports/clients?period=all", headers=auth_headers).json()["data"][
        "rows"
    ]
    row = next(item for item in rows if item["full_name"] == "Только Заведён")

    assert row["category_label"] == "Без заказов"
    assert row["days_since_last_order"] is None
    assert row["orders_count"] == 0


def test_average_days_between_orders(client, auth_headers, directions, db_session):
    manager = manager_id(client, auth_headers)
    client_id = make_client(client, auth_headers, "Ритмичный Клиент", None)
    first = make_order(
        client,
        auth_headers,
        client_id,
        manager,
        "enamel",
        quantity=2,
        amount=1000,
        db_session=db_session,
    )
    make_order(
        client,
        auth_headers,
        client_id,
        manager,
        "enamel",
        quantity=2,
        amount=1000,
        db_session=db_session,
    )

    shift_created_at(db_session, first["id"], days=30)

    rows = client.get("/api/v1/reports/clients?period=all", headers=auth_headers).json()["data"][
        "rows"
    ]
    row = next(item for item in rows if item["full_name"] == "Ритмичный Клиент")

    assert row["average_days_between_orders"] == 30


# --- время изготовления ----------------------------------------------------


def test_production_time_report_is_empty_without_stages(client, auth_headers, directions):
    report = client.get("/api/v1/reports/production-time?period=all", headers=auth_headers).json()[
        "data"
    ]

    assert report["by_stage"] == []
    assert report["orders"] == []


def test_production_time_report_requires_permission(client, no_permission_auth_headers):
    """Роль без прав не открывает ни деньги, ни производство.

    Проверяем именно ролью без прав, а не оператором: по боевому сиду у
    работника цеха есть ``dashboard.read`` и ``production.read`` — он должен
    видеть свою сводку и очередь этапов. Тест, ждавший от оператора отказа,
    сторожил не право доступа, а собственную выдуманную роль.
    """
    for path in ("/api/v1/reports/volume", "/api/v1/reports/production-time"):
        # 403: вошёл, но раздел не его. На 401 фронт увёл бы на страницу входа.
        assert client.get(path, headers=no_permission_auth_headers).status_code == 403


def test_shop_worker_does_not_open_reports(client, operator_auth_headers):
    """Работник цеха отчёты не открывает — ни на экране, ни файлом.

    Раньше отчёты пускали по праву на сводку, а оно у цеха есть ради своих
    этапов и брака. В итоге по прямой ссылке и по клику с плитки «Выручка»
    работник видел выручку студии и выгружал клиентскую базу в Excel — при
    описании роли «Денег и клиентов не видит».
    """
    for path in (
        "/api/v1/reports/volume",
        "/api/v1/reports/clients",
        "/api/v1/reports/volume.xlsx",
        "/api/v1/reports/clients.xlsx",
    ):
        response = client.get(path, headers=operator_auth_headers)
        assert response.status_code == 403, f"{path} открыт работнику цеха"


def test_shop_worker_summary_comes_without_revenue(client, operator_auth_headers):
    """Сводка цеху нужна — этапы и брак, — но без денег студии."""
    data = client.get("/api/v1/dashboard/summary", headers=operator_auth_headers).json()["data"]

    assert data["mock_revenue"] is None
    # Остальное на месте: сводка не должна для цеха опустеть.
    assert "production" in data
    assert data["production"]["active_stages"] is not None


def test_manager_still_sees_revenue(client, manager_auth_headers):
    """Тому, кто ведёт деньги, выручка приходит как приходила."""
    data = client.get("/api/v1/dashboard/summary", headers=manager_auth_headers).json()["data"]

    assert data["mock_revenue"] is not None


def test_work_kind_report_can_be_filtered_by_direction(
    client, auth_headers, directions, db_session
):
    """Отбор направления доходит и до блока «По обработке».

    Заказчик выбирала направление, а таблица обработки считалась по всему
    производству — на экране рядом стояли цифры про шпон и цифры про всё.
    """
    manager = manager_id(client, auth_headers)
    buyer = make_client(client, auth_headers, "Клиент Обработки", None)
    veneer = make_order(
        client,
        auth_headers,
        buyer,
        manager,
        "veneer",
        quantity=2,
        amount=1000,
        db_session=db_session,
    )
    pvc = make_order(
        client, auth_headers, buyer, manager, "pvc", quantity=2, amount=2000, db_session=db_session
    )

    item = client.post(
        "/api/v1/price-book",
        headers=auth_headers,
        json={
            "article": "ОБР-1",
            "name": "Фрезеровка",
            "kind": "milling",
            "unit": "pcs",
            "price": "700.00",
        },
    ).json()["data"]
    for order in (veneer, pvc):
        client.put(
            f"/api/v1/orders/{order['id']}/positions",
            headers=auth_headers,
            json={
                "positions": [
                    {
                        "price_item_id": item["id"],
                        "name": "Фрезеровка",
                        "quantity": "1",
                        "unit": "pcs",
                    }
                ]
            },
        )

    everything = client.get("/api/v1/reports/work-kinds?period=all", headers=auth_headers).json()[
        "data"
    ]
    only_veneer = client.get(
        "/api/v1/reports/work-kinds?period=all&direction_code=veneer", headers=auth_headers
    ).json()["data"]

    assert everything["total"]["orders_count"] == 2
    assert only_veneer["total"]["orders_count"] == 1
    assert Decimal(only_veneer["total"]["amount"]) == Decimal("700.00")
    # Отчёт сам говорит, по какому направлению посчитан — это уходит в шапку файла.
    assert only_veneer["direction_code"] == "veneer"
    assert only_veneer["direction_label"] == "Шпон"


def test_work_kind_report_unknown_direction_is_empty(client, auth_headers, directions, db_session):
    """Направления нет — обработка пустая, а не «вся»."""
    manager = manager_id(client, auth_headers)
    buyer = make_client(client, auth_headers, "Клиент Пустоты", None)
    make_order(
        client, auth_headers, buyer, manager, "pvc", quantity=2, amount=1000, db_session=db_session
    )

    report = client.get(
        "/api/v1/reports/work-kinds?period=all&direction_code=такого-нет", headers=auth_headers
    ).json()["data"]

    assert report["by_kind"] == []
    assert report["total"]["orders_count"] == 0
    # Неизвестный код не подменяем на «все направления»: в шапке файла должно
    # остаться то, что спросили, иначе пустой отчёт читается как «данных нет».
    assert report["direction_label"] == "такого-нет"


def test_production_time_report_accepts_direction(client, auth_headers, directions):
    """Отчёт по этапам принимает тот же отбор, что и остальные — без ошибки."""
    response = client.get(
        "/api/v1/reports/production-time?period=all&direction_code=pvc", headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["direction_code"] == "pvc"
    assert data["direction_label"] == "ПВХ"
    assert data["orders"] == []


# --- периоды ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected_label"),
    [("week", "Неделя"), ("month", "Месяц"), ("quarter", "Квартал"), ("year", "Год")],
)
def test_period_labels(code, expected_label):
    period = resolve_period(code)
    assert period.label == expected_label
    assert period.date_from is not None


def test_quarter_starts_at_quarter_boundary():
    period = resolve_period("quarter", now=datetime(2026, 8, 4, tzinfo=UTC))
    assert period.date_from == datetime(2026, 7, 1, tzinfo=UTC)


def test_week_starts_on_monday():
    # 4 августа 2026 — вторник, значит неделя началась 3 августа
    period = resolve_period("week", now=datetime(2026, 8, 4, tzinfo=UTC))
    assert period.date_from == datetime(2026, 8, 3, tzinfo=UTC)


def test_explicit_dates_win_over_period_code():
    from datetime import date as date_type

    period = resolve_period("year", date_from=date_type(2026, 3, 1), date_to=date_type(2026, 3, 31))
    assert period.code == "custom"
    assert period.date_from == datetime(2026, 3, 1, tzinfo=UTC)
    assert period.date_to.day == 31


def test_month_label_is_russian():
    assert month_label("2026-08") == "август 2026"


def test_total_area_does_not_accumulate_rounding_error(
    client, auth_headers, directions, db_session
):
    """Итог считается по точным площадям, а не по округлённым заказам.

    Регрессия: ``order_areas`` округляла площадь каждого заказа до третьего
    знака, а итог складывался из округлённых значений. На реальных данных
    (716×396 в четырёх заказах ПВХ) это давало 9.639 вместо 9.640 и ломало
    равенство «материал ПВХ = площадь фасадов × 2».
    """
    client_id = make_client(client, auth_headers)
    manager = manager_id(client, auth_headers)

    # 716×396 = 0.283536 м² — площадь с «хвостом» за третьим знаком
    narrow = {
        "item_type": "facade",
        "name": "Фасад",
        "width": "716",
        "height": "396",
        "depth": "19",
    }
    for quantity in (6, 8, 8, 12):
        order = client.post(
            "/api/v1/orders",
            headers=auth_headers,
            json={"client_id": client_id, "manager_id": manager, "direction_code": "pvc"},
        ).json()["data"]
        client.post(
            f"/api/v1/orders/{order['id']}/items",
            headers=auth_headers,
            json={**narrow, "quantity": quantity},
        )

    report = client.get(
        "/api/v1/reports/volume?period=all&metric=accepted", headers=auth_headers
    ).json()["data"]

    facade = Decimal(report["total"]["facade_area_sqm"])
    material = Decimal(report["total"]["material_area_sqm"])

    # 716*396*(6+8+8+12)/1e6 = 9.640224 -> 9.640
    assert facade == Decimal("9.640")
    # у ПВХ плёнка с двух сторон: материал ровно вдвое от площади фасадов
    assert material == facade * 2
