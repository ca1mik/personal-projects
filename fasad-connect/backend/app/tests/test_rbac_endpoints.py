"""Проверка разграничения доступа по ролям.

Заказчик поймал систему на том, что менеджер, технолог и работник цеха имеют
одинаковый доступ: любой сотрудник с логином мог удалить оплату по заказу,
поменять смету или выгрузить взаиморасчёты клиента. Роли в админке рисовались
галочками, но ни одна галочка ни на что не влияла.

Здесь зафиксировано, кто и что имеет право открыть. Матрица идёт по ролям, а не
по эндпоинтам: логин каждой роли стоит нескольких хешей пароля, и прогон
«эндпоинт × роль» отдельными тестами превращал набор в минуты ожидания.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi.routing import APIRoute

from app.main import app
from scripts.seed import ROLE_PERMISSION_MAP

# Несуществующий идентификатор: проверяем только допуск к эндпоинту, поэтому
# 404 или 422 для разрешённой роли — нормальный ответ, отказ доступа — нет.
MISSING_ID = "00000000-0000-0000-0000-000000000000"

# Отказ по правам — 403, а не 401. Разница видна пользователю: на 401 фронт
# считает, что сессия протухла, и уводит на страницу входа, а работник цеха,
# открывший чужой раздел по прямой ссылке, попадал в петлю «войди — снова
# войди». 403 оставляет его в системе и показывает «Недостаточно прав».
DENIED = 403
#: Не вошёл вовсе. Отдельно от DENIED специально: интерфейс на них реагирует
#: по-разному, и путать их нельзя.
UNAUTHORIZED = 401

# (метод, путь, роли, которым эндпоинт разрешён)
ACCESS_MATRIX: list[tuple[str, str, set[str]]] = [
    # --- заказы -------------------------------------------------------------
    ("GET", "/api/v1/orders/statuses", {"manager", "technologist", "operator"}),
    ("GET", "/api/v1/orders/payment-methods", {"manager", "technologist"}),
    # Список заказов — это суммы по всем заказам разом, то есть выручка студии.
    # Цеху он не нужен: свой заказ работник открывает из этапа, карточкой.
    ("GET", "/api/v1/orders", {"manager", "technologist"}),
    ("POST", "/api/v1/orders", {"manager", "technologist"}),
    ("GET", f"/api/v1/orders/{MISSING_ID}", {"manager", "technologist", "operator"}),
    ("PATCH", f"/api/v1/orders/{MISSING_ID}", {"manager", "technologist"}),
    ("POST", f"/api/v1/orders/{MISSING_ID}/items", {"manager", "technologist"}),
    ("POST", f"/api/v1/orders/{MISSING_ID}/generate-parts", {"manager", "technologist"}),
    ("POST", f"/api/v1/orders/{MISSING_ID}/calculate", {"manager", "technologist"}),
    ("POST", f"/api/v1/orders/{MISSING_ID}/change-status", {"manager", "technologist"}),
    ("POST", f"/api/v1/orders/{MISSING_ID}/reserve-stock", {"manager", "technologist"}),
    ("POST", f"/api/v1/orders/{MISSING_ID}/writeoff-stock", {"manager", "technologist"}),
    ("PUT", f"/api/v1/orders/{MISSING_ID}/positions", {"manager", "technologist"}),
    ("POST", f"/api/v1/orders/{MISSING_ID}/payments", {"manager", "technologist"}),
    (
        "DELETE",
        f"/api/v1/orders/{MISSING_ID}/payments/{MISSING_ID}",
        {"manager", "technologist"},
    ),
    ("POST", f"/api/v1/orders/{MISSING_ID}/additional", {"manager", "technologist"}),
    ("POST", f"/api/v1/orders/{MISSING_ID}/material-ordered", {"manager", "technologist"}),
    ("POST", f"/api/v1/orders/{MISSING_ID}/shipped", {"manager", "technologist"}),
    ("POST", f"/api/v1/orders/{MISSING_ID}/save-cutting-layout", {"manager", "technologist"}),
    # --- клиенты ------------------------------------------------------------
    ("GET", "/api/v1/clients", {"manager", "technologist"}),
    ("POST", "/api/v1/clients", {"manager"}),
    ("GET", f"/api/v1/clients/{MISSING_ID}", {"manager", "technologist"}),
    ("PATCH", f"/api/v1/clients/{MISSING_ID}", {"manager"}),
    ("POST", f"/api/v1/clients/{MISSING_ID}/deposit", {"manager", "technologist"}),
    ("POST", f"/api/v1/clients/{MISSING_ID}/deposit/withdraw", {"manager"}),
    ("GET", f"/api/v1/clients/{MISSING_ID}/statement.xlsx", {"manager"}),
    # --- справочник изделий и калькуляторы ----------------------------------
    ("GET", "/api/v1/templates", {"manager", "technologist"}),
    ("POST", "/api/v1/templates", {"technologist"}),
    ("GET", "/api/v1/templates/catalog", {"manager", "technologist"}),
    ("POST", "/api/v1/templates/catalog/estimate", {"manager", "technologist"}),
    ("POST", "/api/v1/templates/catalog/lead", {"manager"}),
    ("GET", "/api/v1/templates/film-cutting/options", {"manager", "technologist"}),
    ("POST", "/api/v1/templates/film-cutting/estimate", {"manager", "technologist"}),
    ("POST", "/api/v1/templates/film-cutting/lead", {"manager"}),
    # --- склад --------------------------------------------------------------
    ("GET", "/api/v1/stock/items", {"technologist"}),
    ("GET", "/api/v1/stock/movements", {"technologist"}),
    # --- файлы заказа -------------------------------------------------------
    ("GET", f"/api/v1/orders/{MISSING_ID}/files", {"manager", "technologist", "operator"}),
    ("POST", f"/api/v1/orders/{MISSING_ID}/files", {"manager", "technologist"}),
    (
        "GET",
        f"/api/v1/documents/{MISSING_ID}/download",
        {"manager", "technologist", "operator"},
    ),
    ("PATCH", f"/api/v1/documents/{MISSING_ID}", {"manager", "technologist"}),
    ("DELETE", f"/api/v1/documents/{MISSING_ID}", {"manager", "technologist"}),
    # --- разбор бланка заказчика --------------------------------------------
    ("POST", "/api/v1/imports/parts", {"manager", "technologist"}),
    # --- сводки -------------------------------------------------------------
    ("GET", "/api/v1/dashboard/summary", {"manager", "technologist", "operator"}),
    ("GET", "/api/v1/dashboard/production", {"manager", "technologist", "operator"}),
    # --- заявки ---------------------------------------------------------------
    ("GET", "/api/v1/leads", {"manager", "technologist"}),
    ("GET", f"/api/v1/leads/{MISSING_ID}", {"manager", "technologist"}),
    ("GET", f"/api/v1/leads/{MISSING_ID}/blank.xlsx", {"manager", "technologist"}),
    ("PATCH", f"/api/v1/leads/{MISSING_ID}", {"manager"}),
    ("POST", f"/api/v1/leads/{MISSING_ID}/create-order", {"manager", "technologist"}),
    # --- отчёты ---------------------------------------------------------------
    # Закрыты своим правом, а не правом на сводку: это выручка, объёмы и
    # клиентская база. Работник цеха их не открывает.
    ("GET", "/api/v1/reports/volume", {"manager", "technologist"}),
    ("GET", "/api/v1/reports/clients", {"manager", "technologist"}),
    ("GET", "/api/v1/reports/orders", {"manager", "technologist"}),
    ("GET", "/api/v1/reports/work-kinds", {"manager", "technologist"}),
    ("GET", "/api/v1/reports/volume.xlsx", {"manager", "technologist"}),
    ("GET", "/api/v1/reports/clients.xlsx", {"manager", "technologist"}),
    # --- справочник цен -------------------------------------------------------
    # Прайс — это деньги. Цеху он не нужен и по описанию роли не положен.
    ("GET", "/api/v1/price-book", {"manager", "technologist"}),
    ("GET", "/api/v1/price-book/options", {"manager", "technologist"}),
    ("POST", "/api/v1/price-book", {"manager", "technologist"}),
    # --- подсказки таблицы расчёта --------------------------------------------
    ("GET", "/api/v1/reference-values", {"manager", "technologist"}),
    # --- справочники материалов -----------------------------------------------
    # Читать может каждая рабочая роль: по ним сверяются в цехе. Но не роль без
    # прав — новая роль не должна открывать ничего. Заводить новую позицию —
    # работа того, кто ведёт справочники: от них считается заказ.
    ("GET", "/api/v1/materials", {"manager", "technologist", "operator"}),
    ("POST", "/api/v1/materials", {"technologist"}),
    ("GET", "/api/v1/hardware", {"manager", "technologist", "operator"}),
    ("POST", "/api/v1/hardware", {"technologist"}),
    # --- подготовка производства по заказу ------------------------------------
    ("POST", f"/api/v1/orders/{MISSING_ID}/export-cutting", {"manager", "technologist"}),
    ("POST", f"/api/v1/orders/{MISSING_ID}/generate-cnc", {"manager", "technologist"}),
    ("GET", f"/api/v1/orders/{MISSING_ID}/parts", {"manager", "technologist", "operator"}),
    ("GET", f"/api/v1/orders/{MISSING_ID}/exports", {"manager", "technologist", "operator"}),
    ("GET", f"/api/v1/orders/{MISSING_ID}/cnc-jobs", {"manager", "technologist", "operator"}),
]


def _check_role(client, headers: dict[str, str], role_code: str) -> list[str]:
    """Прогоняет всю матрицу под одной ролью и возвращает список расхождений.

    Сразу собираем все расхождения: иначе после первой же дырки в правах
    приходится чинить по одному эндпоинту за прогон.
    """
    problems: list[str] = []
    for method, path, allowed_roles in ACCESS_MATRIX:
        response = client.request(method, path, headers=headers)
        allowed = role_code in allowed_roles
        if allowed and response.status_code == DENIED:
            problems.append(f"{role_code}: {method} {path} закрыт, а должен быть открыт")
        if not allowed and response.status_code != DENIED:
            problems.append(
                f"{role_code}: {method} {path} открыт ({response.status_code}), "
                "а должен быть закрыт"
            )
    return problems


def test_manager_access_matrix(client, manager_auth_headers):
    """Менеджер ведёт клиентов, заявки, заказы и деньги, но не склад."""
    assert _check_role(client, manager_auth_headers, "manager") == []


def test_technologist_access_matrix(client, technologist_auth_headers):
    """Технолог ведёт справочник изделий и склад, но не заводит клиентов."""
    assert _check_role(client, technologist_auth_headers, "technologist") == []


def test_operator_access_matrix(client, operator_auth_headers):
    """Работник цеха видит заказ и его файлы, но не деньги, склад и клиентов."""
    assert _check_role(client, operator_auth_headers, "operator") == []


def test_role_without_permissions_is_denied_everywhere(client, no_permission_auth_headers):
    """Новая роль без галочек не должна получать доступ ни к чему по умолчанию."""
    problems = [
        f"{method} {path} открыт для роли без прав"
        for method, path, _ in ACCESS_MATRIX
        if client.request(method, path, headers=no_permission_auth_headers).status_code != DENIED
    ]
    assert problems == []


def test_anonymous_request_is_unauthorized_not_forbidden(client):
    """Без токена — 401, а не 403. Эти два ответа разводят интерфейс по-разному.

    401 значит «войди»: фронт уводит на страницу входа. 403 значит «вошёл, но
    раздел не твой»: человек остаётся в системе и видит «Недостаточно прав».
    Пока оба случая отвечали 401, работник цеха, открывший чужой раздел, попадал
    на форму входа, вводил верный пароль и снова видел форму.
    """
    assert client.get("/api/v1/orders").status_code == UNAUTHORIZED
    assert client.get("/api/v1/dashboard/summary").status_code == UNAUTHORIZED
    assert UNAUTHORIZED != DENIED


# --- happy path: роль действительно работает --------------------------------


def test_manager_lists_clients_and_orders(client, manager_auth_headers):
    clients = client.get("/api/v1/clients?page=1&size=10", headers=manager_auth_headers)
    orders = client.get("/api/v1/orders?page=1&size=10", headers=manager_auth_headers)

    assert clients.status_code == 200
    assert orders.status_code == 200
    assert isinstance(clients.json()["data"], list)


def test_technologist_lists_stock(client, technologist_auth_headers):
    items = client.get("/api/v1/stock/items?page=1&size=10", headers=technologist_auth_headers)
    movements = client.get(
        "/api/v1/stock/movements?page=1&size=10", headers=technologist_auth_headers
    )

    assert items.status_code == 200
    assert movements.status_code == 200


def test_operator_sees_shop_floor_but_not_money(client, operator_auth_headers):
    """Главная жалоба заказчика: цех не должен открывать деньги и клиентов."""
    production = client.get("/api/v1/dashboard/production", headers=operator_auth_headers)

    assert production.status_code == 200
    assert client.get("/api/v1/clients", headers=operator_auth_headers).status_code == DENIED
    assert (
        client.get("/api/v1/orders/payment-methods", headers=operator_auth_headers).status_code
        == DENIED
    )


def test_auth_me_returns_role_permissions(client, operator_auth_headers):
    """Меню в интерфейсе строится по правам из /auth/me — они обязаны там быть.

    Без этого списка фронт снова покажет всем одинаковые пятнадцать пунктов.
    """
    data = client.get("/api/v1/auth/me", headers=operator_auth_headers).json()["data"]
    codes = {item["code"] for item in data["role"]["permissions"]}

    assert data["role"]["code"] == "operator"
    assert codes == set(ROLE_PERMISSION_MAP["operator"])


# --- права из seed.py не должны быть декоративными --------------------------


def _iter_api_routes(router: object, seen: set[int] | None = None) -> Iterator[APIRoute]:
    """Все APIRoute приложения, включая вложенные роутеры.

    Раньше здесь хватало плоского обхода ``app.routes``. В новых версиях FastAPI
    ``include_router`` больше не разворачивает маршруты в список приложения, а
    кладёт туда обёртку (``_IncludedRouter``), которая держит исходный роутер в
    ``original_router``. Плоский обход после этого видел ровно два маршрута —
    ``/health`` и ``/`` — и тест уверенно сообщал, что ни одно право ничего не
    закрывает, хотя проверки на месте и матрица ролей выше проходила.

    Поэтому спускаемся по любому вложенному роутеру, какой найдём, и не
    привязываемся к имени внутреннего класса: переживёт и следующее
    переименование внутри FastAPI.
    """
    if seen is None:
        seen = set()
    if id(router) in seen:
        return
    seen.add(id(router))

    for route in getattr(router, "routes", []):
        if isinstance(route, APIRoute):
            yield route
        for attribute in ("original_router", "router", "app"):
            nested = getattr(route, attribute, None)
            if nested is not None and hasattr(nested, "routes"):
                yield from _iter_api_routes(nested, seen)


def _permission_codes_used_by_routes() -> set[str]:
    """Собирает коды прав, реально навешенные на маршруты через require_permissions.

    Коды лежат в замыкании зависимости, другого способа увидеть их снаружи нет.
    Проверка нужна, чтобы право из seed.py не осталось галочкой в админке,
    которая ничего не закрывает.
    """
    codes: set[str] = set()
    for route in _iter_api_routes(app):
        pending = list(route.dependant.dependencies)
        while pending:
            dependant = pending.pop()
            for cell in getattr(dependant.call, "__closure__", None) or ():
                value = cell.cell_contents
                if isinstance(value, tuple) and all(isinstance(item, str) for item in value):
                    codes.update(value)
            pending.extend(dependant.dependencies)
    return codes


def test_route_walk_sees_the_whole_api():
    """Страховка для теста ниже: обход обязан находить сами маршруты.

    Когда FastAPI перестал разворачивать include_router, обход находил два
    маршрута из ста с лишним — и проверка прав превращалась в «ничего не нашли,
    значит всё плохо». Сломайся обход в другую сторону (пустое множество прав
    сравнивается с пустым), тест прав прошёл бы молча и вообще ничего не
    проверял. Поэтому число маршрутов проверяем отдельно: порог заведомо ниже
    реального (сейчас их 128), он ловит именно обвал обхода, а не рост API.
    """
    assert len(list(_iter_api_routes(app))) > 50


def test_every_seeded_permission_guards_some_endpoint():
    used = _permission_codes_used_by_routes()
    unused = sorted(set(ROLE_PERMISSION_MAP["admin"]) - used)

    assert unused == [], f"права заведены, но ничего не закрывают: {unused}"
