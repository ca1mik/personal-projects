from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.modules.order_statuses.models import OrderStatus
from app.modules.shared.numbering import allocate, peek


def make_order(client, headers, number=None):
    lead = client.post("/api/v1/leads/intake", json={"source_channel": "manual_manager_input", "text": "Name: Workflow Client, phone +79990000000"}).json()["data"]
    result = client.post(f"/api/v1/leads/{lead['id']}/create-order", json={"order_number": number}, headers=headers)
    assert result.status_code == 200, result.text
    return lead, result.json()["data"]


def test_lifecycle_accepts_unpaid_order_and_filters(client, auth_headers, db_session):
    for code in ("waiting_client", "accepted"):
        db_session.add(OrderStatus(code=code, name=code, sort_order=25, is_terminal=False))
    db_session.commit()
    _, order = make_order(client, auth_headers, "3476")
    assert order["lifecycle"] == "estimate"
    for code, lifecycle in (("waiting_client", "waiting"), ("accepted", "in_work")):
        result = client.post(f"/api/v1/orders/{order['id']}/change-status", json={"status_code": code}, headers=auth_headers)
        assert result.status_code == 200, result.text
        data = result.json()["data"]
        assert data["lifecycle"] == lifecycle
        assert data["payments"] == [] and data["production_start_at"] is None
        rows = client.get(f"/api/v1/orders?lifecycle={lifecycle}", headers=auth_headers).json()["data"]
        assert [row["id"] for row in rows] == [order["id"]]
    assert client.get("/api/v1/orders?lifecycle=estimate", headers=auth_headers).json()["data"] == []


def test_order_trash_restore_and_number_history(client, auth_headers):
    _, first = make_order(client, auth_headers, "3476")
    path = f"/api/v1/orders/{first['id']}"
    assert client.delete(path, headers=auth_headers).status_code == 200
    assert client.get("/api/v1/orders", headers=auth_headers).json()["data"] == []
    assert client.get("/api/v1/orders?deleted=true", headers=auth_headers).json()["data"][0]["id"] == first["id"]
    assert client.patch(path, json={"comment": "must not edit trash"}, headers=auth_headers).status_code == 404
    assert client.post(path + "/payments", json={"amount": 1, "method": "cash"}, headers=auth_headers).status_code == 404
    history = client.get(f"/api/v1/clients/{first['client_id']}", headers=auth_headers).json()["data"]
    assert all(o["id"] != first["id"] for o in history.get("orders", []))
    _, second = make_order(client, auth_headers)
    assert second["order_number"] == "3477"
    assert client.post(path + "/restore", headers=auth_headers).status_code == 200
    assert client.get(path, headers=auth_headers).json()["data"]["deleted_at"] is None
    assert client.get(f"/api/v1/clients/{first['client_id']}", headers=auth_headers).status_code == 200


def test_delete_lead_keeps_order_and_client(client, auth_headers):
    lead, order = make_order(client, auth_headers)
    path = f"/api/v1/leads/{lead['id']}"
    assert client.delete(path, headers=auth_headers).status_code == 200
    assert client.get("/api/v1/leads", headers=auth_headers).json()["data"] == []
    assert client.get("/api/v1/leads?deleted=true", headers=auth_headers).json()["data"][0]["id"] == lead["id"]
    assert client.get(f"/api/v1/orders/{order['id']}", headers=auth_headers).status_code == 200
    assert client.get(f"/api/v1/clients/{order['client_id']}", headers=auth_headers).status_code == 200
    assert client.post(path + "/restore", headers=auth_headers).status_code == 200
    assert client.get("/api/v1/leads", headers=auth_headers).json()["data"][0]["id"] == lead["id"]


def test_money_and_production_orders_cannot_be_deleted(client, auth_headers):
    _, paid = make_order(client, auth_headers)
    path = f"/api/v1/orders/{paid['id']}"
    assert client.post(path + "/payments", json={"amount": 10, "method": "cash"}, headers=auth_headers).status_code == 200
    assert client.delete(path, headers=auth_headers).status_code == 409
    _, started = make_order(client, auth_headers)
    path = f"/api/v1/orders/{started['id']}"
    client.post(path + "/change-status", json={"status_code": "manufacturing"}, headers=auth_headers)
    assert client.delete(path, headers=auth_headers).status_code == 409


def test_parent_child_restore_order(client, auth_headers):
    _, parent = make_order(client, auth_headers)
    path = f"/api/v1/orders/{parent['id']}"
    child = client.post(path + "/additional", json={}, headers=auth_headers).json()["data"]
    assert client.delete(path, headers=auth_headers).status_code == 409
    assert client.delete(f"/api/v1/orders/{child['id']}", headers=auth_headers).status_code == 200
    assert client.delete(path, headers=auth_headers).status_code == 200
    assert client.post(f"/api/v1/orders/{child['id']}/restore", headers=auth_headers).status_code == 409
    assert client.post(path + "/restore", headers=auth_headers).status_code == 200
    assert client.post(f"/api/v1/orders/{child['id']}/restore", headers=auth_headers).status_code == 200


def test_permissions_cannot_delete_documents(client, auth_headers, operator_auth_headers):
    lead, order = make_order(client, auth_headers)
    for kind, identifier in (("orders", order["id"]), ("leads", lead["id"])):
        assert client.delete(f"/api/v1/{kind}/{identifier}", headers=operator_auth_headers).status_code == 403
        assert client.post(f"/api/v1/{kind}/{identifier}/restore", headers=operator_auth_headers).status_code == 403


def test_concurrent_allocations_and_preview_do_not_reuse_numbers(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'counter.db'}", connect_args={"timeout": 30})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        assert peek(db, "orders") == peek(db, "orders") == 1
        db.commit()
    def next_number(_):
        with Session(engine) as db:
            value = allocate(db, "orders")
            db.commit()
            return value
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert sorted(pool.map(next_number, range(18))) == list(range(1, 19))
    engine.dispose()
