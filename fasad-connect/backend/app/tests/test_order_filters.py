"""Фильтры списка заказов, включая форму номера.

Заказчик различает типы заказов по виду номера: «0001» просто номер,
«0001-П» номер и буква, «0001-ОШ» номер и две буквы.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.modules.directions.models import ProductionDirection
from app.modules.orders.models import Order

DIRECTIONS = [
    # код, имя, буква, коэффициент площади
    ("enamel", "Эмаль", "", Decimal("1")),
    ("pvc", "ПВХ", "П", Decimal("2")),
    ("veneer", "Шпон", "Ш", Decimal("1")),
    ("enamel_veneer", "Эмаль по шпону", "ОШ", Decimal("1")),
]


@pytest.fixture
def directions(db_session):
    for index, (code, name, suffix, factor) in enumerate(DIRECTIONS):
        db_session.add(
            ProductionDirection(
                code=code,
                name=name,
                number_suffix=suffix,
                material_area_factor=factor,
                sort_order=(index + 1) * 10,
                is_active=True,
            )
        )
    db_session.commit()


@pytest.fixture
def catalog(client, auth_headers, directions):
    """По одному заказу на каждое направление плюс заказ без направления."""
    manager = client.get("/api/v1/admin/users?page=1&size=5", headers=auth_headers).json()["data"][
        0
    ]["id"]
    first = client.post(
        "/api/v1/clients",
        headers=auth_headers,
        json={"full_name": "Первый Клиент", "organization": "ООО «Первая»"},
    ).json()["data"]["id"]
    second = client.post(
        "/api/v1/clients",
        headers=auth_headers,
        json={"full_name": "Второй Клиент", "organization": "ИП Второй"},
    ).json()["data"]["id"]

    created = {}
    for code, _name, _suffix, _factor in DIRECTIONS:
        response = client.post(
            "/api/v1/orders",
            headers=auth_headers,
            json={
                "client_id": first if code in {"enamel", "pvc"} else second,
                "manager_id": manager,
                "direction_code": code,
            },
        )
        created[code] = response.json()["data"]

    created["no_direction"] = client.post(
        "/api/v1/orders",
        headers=auth_headers,
        json={"client_id": second, "manager_id": manager},
    ).json()["data"]

    return created


def numbers(client, auth_headers, query: str) -> list[str]:
    response = client.get(f"/api/v1/orders?page=1&size=50&{query}", headers=auth_headers)
    assert response.status_code == 200, response.text
    return [item["order_number"] for item in response.json()["data"]]


# --- номер с двумя буквами -------------------------------------------------


def test_two_letter_direction_produces_two_letter_number(catalog):
    assert catalog["enamel_veneer"]["order_number"].endswith("-ОШ")
    assert catalog["enamel_veneer"]["direction"]["name"] == "Эмаль по шпону"


def test_all_number_forms_coexist(catalog):
    assert catalog["enamel"]["order_number"].isdigit()
    assert catalog["pvc"]["order_number"].endswith("-П")
    assert catalog["veneer"]["order_number"].endswith("-Ш")
    assert catalog["enamel_veneer"]["order_number"].endswith("-ОШ")
    assert catalog["no_direction"]["order_number"].isdigit()


# --- фильтр по форме номера ------------------------------------------------


def test_filter_plain_numbers(client, auth_headers, catalog):
    """«Просто номер» — эмаль и заказы без направления."""
    result = numbers(client, auth_headers, "number_shape=plain")

    assert len(result) == 2
    assert all(number.isdigit() for number in result)


def test_filter_single_letter_numbers(client, auth_headers, catalog):
    result = numbers(client, auth_headers, "number_shape=letter")

    assert sorted(result) == sorted(
        [catalog["pvc"]["order_number"], catalog["veneer"]["order_number"]]
    )


def test_filter_two_letter_numbers(client, auth_headers, catalog):
    result = numbers(client, auth_headers, "number_shape=double")

    assert result == [catalog["enamel_veneer"]["order_number"]]


def test_unknown_number_shape_is_ignored(client, auth_headers, catalog):
    """Неизвестное значение не должно молча прятать заказы."""
    result = numbers(client, auth_headers, "number_shape=triple")

    assert len(result) == 5


# --- фильтр по направлению -------------------------------------------------


def test_filter_by_direction_code(client, auth_headers, catalog):
    result = numbers(client, auth_headers, "direction_code=pvc")

    assert result == [catalog["pvc"]["order_number"]]


def test_filter_orders_without_direction(client, auth_headers, catalog):
    result = numbers(client, auth_headers, "direction_code=none")

    assert result == [catalog["no_direction"]["order_number"]]


def test_filter_by_unknown_direction_returns_empty(client, auth_headers, catalog):
    assert numbers(client, auth_headers, "direction_code=acrylic") == []


# --- поиск и прочие фильтры ------------------------------------------------


def test_search_finds_order_by_client_name(client, auth_headers, catalog):
    result = numbers(client, auth_headers, "search=второй")

    assert len(result) == 3
    assert catalog["no_direction"]["order_number"] in result


def test_search_finds_order_by_organization(client, auth_headers, catalog):
    result = numbers(client, auth_headers, "search=первая")

    assert sorted(result) == sorted(
        [catalog["enamel"]["order_number"], catalog["pvc"]["order_number"]]
    )


def test_search_finds_order_by_number(client, auth_headers, catalog):
    target = catalog["enamel_veneer"]["order_number"]

    assert numbers(client, auth_headers, f"search={target}") == [target]


def test_filter_by_client(client, auth_headers, catalog):
    order = catalog["pvc"]
    result = numbers(client, auth_headers, f"client_id={order['client_id']}")

    assert len(result) == 2


def test_filter_by_date_range(client, auth_headers, catalog, db_session):
    old = db_session.get(Order, uuid.UUID(catalog["veneer"]["id"]))
    old.created_at = datetime.now(UTC) - timedelta(days=45)
    db_session.commit()

    today = datetime.now(UTC).date()
    recent = numbers(client, auth_headers, f"date_from={today - timedelta(days=7)}")
    everything = numbers(client, auth_headers, "")

    assert len(everything) == 5
    assert len(recent) == 4
    assert catalog["veneer"]["order_number"] not in recent


def test_filters_combine(client, auth_headers, catalog):
    """Форма номера и клиент работают вместе, а не по отдельности."""
    order = catalog["pvc"]
    result = numbers(client, auth_headers, f"number_shape=letter&client_id={order['client_id']}")

    assert result == [order["order_number"]]


def test_pagination_meta_respects_filters(client, auth_headers, catalog):
    response = client.get("/api/v1/orders?page=1&size=50&number_shape=double", headers=auth_headers)

    assert response.json()["meta"]["total"] == 1


# --- сортировка по сроку ----------------------------------------------------
# Заказчик: клик по заголовку «Срок» в списке заказов должен сортировать
# ближе-дальше в обе стороны, а заказы без срока — не путаться среди
# отсортированных, они не «ближе всех», их просто ещё не назвали.


def test_sort_by_due_date_ascending_puts_soonest_first(client, auth_headers, catalog):
    enamel = catalog["enamel"]["id"]
    pvc = catalog["pvc"]["id"]
    veneer = catalog["veneer"]["id"]  # срок не проставлен

    client.patch(f"/api/v1/orders/{enamel}", headers=auth_headers, json={"due_date": "2026-09-20"})
    client.patch(f"/api/v1/orders/{pvc}", headers=auth_headers, json={"due_date": "2026-09-10"})

    response = client.get(
        "/api/v1/orders?page=1&size=50&sort_by=due_date&sort_dir=asc", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    ids = [item["id"] for item in response.json()["data"]]

    assert ids.index(pvc) < ids.index(enamel)
    # Без срока — в хвосте списка даже при сортировке «по возрастанию».
    assert ids.index(enamel) < ids.index(veneer)


def test_sort_by_due_date_descending_puts_latest_first(client, auth_headers, catalog):
    enamel = catalog["enamel"]["id"]
    pvc = catalog["pvc"]["id"]

    client.patch(f"/api/v1/orders/{enamel}", headers=auth_headers, json={"due_date": "2026-09-20"})
    client.patch(f"/api/v1/orders/{pvc}", headers=auth_headers, json={"due_date": "2026-09-10"})

    response = client.get(
        "/api/v1/orders?page=1&size=50&sort_by=due_date&sort_dir=desc", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    ids = [item["id"] for item in response.json()["data"]]

    assert ids.index(enamel) < ids.index(pvc)


def test_unknown_sort_by_is_ignored_not_rejected(client, auth_headers, catalog):
    """Незнакомое имя сортировки не роняет список — просто сортирует как обычно."""
    response = client.get("/api/v1/orders?page=1&size=50&sort_by=nonsense", headers=auth_headers)

    assert response.status_code == 200, response.text


def test_sort_dir_rejects_unknown_direction(client, auth_headers, catalog):
    response = client.get(
        "/api/v1/orders?page=1&size=50&sort_by=due_date&sort_dir=upwards", headers=auth_headers
    )

    assert response.status_code == 422


# --- уникальность буквы ----------------------------------------------------


def test_two_letter_suffix_must_also_be_unique(client, auth_headers, directions):
    response = client.post(
        "/api/v1/directions",
        headers=auth_headers,
        json={
            "code": "enamel_veneer_matte",
            "name": "Эмаль по шпону матовая",
            "number_suffix": "ОШ",
        },
    )

    assert response.status_code == 409
    assert "Эмаль по шпону" in response.json()["error"]["message"]


def test_new_two_letter_direction_can_be_created(client, auth_headers, directions):
    response = client.post(
        "/api/v1/directions",
        headers=auth_headers,
        json={
            "code": "acrylic_gloss",
            "name": "Акрил глянец",
            "number_suffix": "АГ",
            "material_area_factor": "1.5",
            "sort_order": 50,
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["number_suffix"] == "АГ"
