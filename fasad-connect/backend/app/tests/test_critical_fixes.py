from __future__ import annotations

import sqlite3
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.modules.production.models import EdgeMaterial, Material
from app.modules.orders.models import OrderItem
from app.modules.parts_generator.models import Part, PartEdge
from app.modules.stock.models import StockItem, StockMovement
from app.modules.users.models import User
from scripts.seed import upsert_user
from scripts.backup import create_snapshot, restore, status, verify


def _order(client, auth_headers):
    lead = client.post("/api/v1/leads/intake", json={
        "source_channel": "website_form", "text": "Name: Critical Test, phone +79990001122",
    })
    assert lead.status_code == 200, lead.text
    response = client.post(
        f"/api/v1/leads/{lead.json()['data']['id']}/create-order",
        json={}, headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


def test_facade_calculation_keeps_position_amount_without_edge_material(client, auth_headers, db_session):
    order_id = _order(client, auth_headers)
    response = client.put(f"/api/v1/orders/{order_id}/positions", json={"positions": [
        {"name": "Белый софт", "is_custom": True, "unit_price": "1234.00", "quantity": "2", "width": "1000", "height": "500", "color": "Белый софт", "milling": "арт. 110", "thickness": "16"},
    ]}, headers=auth_headers)
    assert response.status_code == 200, response.text
    db_session.execute(delete(EdgeMaterial))
    db_session.commit()

    calculated = client.post(f"/api/v1/orders/{order_id}/calculate", headers=auth_headers)
    assert calculated.status_code == 200, calculated.text
    data = calculated.json()["data"]
    assert data["total_amount"] == "1234.00"
    assert data["final_amount"] == "1234.00"
    assert data["components"][0]["name"] == "Белый софт"


def test_empty_order_calculation_clears_total(client, auth_headers):
    order_id = _order(client, auth_headers)
    response = client.post(f"/api/v1/orders/{order_id}/calculate", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["total_amount"] == "0.00"


@pytest.mark.parametrize("placements", [
    [{"unitId": "a", "x": 10, "y": 10, "width": 100, "height": 100}, {"unitId": "b", "x": 50, "y": 50, "width": 100, "height": 100}],
    [{"unitId": "a", "x": 950, "y": 10, "width": 100, "height": 100}],
    [{"unitId": "a", "x": 10, "y": 10, "width": 100, "height": 100}, {"unitId": "a", "x": 200, "y": 10, "width": 100, "height": 100}],
])
def test_invalid_cutting_layout_is_rejected(client, auth_headers, placements):
    order_id = _order(client, auth_headers)
    response = client.post(f"/api/v1/orders/{order_id}/save-cutting-layout", json={
        "sheet_settings": {"sheetWidth": 1000, "sheetHeight": 500},
        "sheets": [{"placements": placements}],
    }, headers=auth_headers)
    assert response.status_code == 422, response.text


def test_valid_cutting_layout_is_saved(client, auth_headers):
    order_id = _order(client, auth_headers)
    response = client.post(f"/api/v1/orders/{order_id}/save-cutting-layout", json={
        "sheet_settings": {"sheetWidth": 1000, "sheetHeight": 500, "defaultGapX": 60},
        "sheets": [{"placements": [
            {"unitId": "a", "x": 10, "y": 10, "width": 100, "height": 100},
            {"unitId": "b", "x": 170, "y": 10, "width": 100, "height": 100},
        ]}],
    }, headers=auth_headers)
    assert response.status_code == 200, response.text


def test_cutting_layout_cannot_claim_unplaced_parts_are_placed(client, auth_headers):
    order_id = _order(client, auth_headers)
    response = client.post(f"/api/v1/orders/{order_id}/save-cutting-layout", json={
        "sheet_settings": {"sheetWidth": 1000, "sheetHeight": 500},
        "stats": {"sheetCount": 1, "requestedCount": 2, "placedCount": 2, "unplacedCount": 0},
        "parts": [{"name": "Фасад", "width": 100, "height": 100, "quantity": 2}],
        "sheets": [{"placements": []}],
    }, headers=auth_headers)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("route", [
    "/api/v1/leads/intake", "/api/v1/messaging/email/intake",
    "/api/v1/messaging/telegram/webhook", "/api/v1/messaging/telegram/bot/webhook",
    "/api/v1/messaging/telegram/bot/telegram-api", "/api/v1/messaging/whatsapp/webhook",
    "/api/v1/messaging/webhook/intake",
])
def test_public_intake_requires_credentials(client, route):
    client.headers.pop("X-Fasad-Webhook-Token")
    response = client.post(route, json={})
    assert response.status_code == 401, response.text


def test_staff_can_create_lead_without_webhook_secret(client, auth_headers):
    client.headers.pop("X-Fasad-Webhook-Token")
    response = client.post("/api/v1/leads/intake", json={
        "source_channel": "manual", "text": "Name: Staff, phone +79990001123",
    }, headers=auth_headers)
    assert response.status_code == 200, response.text


def test_public_intake_body_limit(client, monkeypatch):
    from app.core import intake_guard

    monkeypatch.setattr(intake_guard, "MAX_BODY_BYTES", 100)
    response = client.post("/api/v1/leads/intake", json={"source_channel": "manual", "text": "x" * 200})
    assert response.status_code == 413, response.text


def test_public_intake_rate_limit(client, monkeypatch):
    from app.core import intake_guard

    monkeypatch.setattr(intake_guard, "MAX_REQUESTS_PER_MINUTE", 2)
    for _ in range(2):
        assert client.post("/api/v1/leads/intake", json={}).status_code == 422
    assert client.post("/api/v1/leads/intake", json={}).status_code == 429


def test_verified_backup_and_staged_restore(tmp_path: Path):
    settings = get_settings()
    original_db, original_storage, original_mirror = settings.database_url, settings.local_storage_path, settings.backup_mirror_path
    database = tmp_path / "source.sqlite"
    storage = tmp_path / "files"
    storage.mkdir()
    (storage / "drawing.txt").write_text("first", encoding="utf-8")
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE orders (number TEXT)")
        connection.execute("INSERT INTO orders VALUES ('A-1')")
    settings.database_url = f"sqlite:///{database.as_posix()}"
    settings.local_storage_path = storage
    settings.backup_mirror_path = tmp_path / "external-drive"
    try:
        snapshot = create_snapshot(tmp_path / "backups")
        verify(snapshot)
        verify(settings.backup_mirror_path / snapshot.name)
        assert status(tmp_path / "backups")["mirror"].endswith(snapshot.name)
        with sqlite3.connect(database) as connection:
            connection.execute("DELETE FROM orders")
        (storage / "drawing.txt").write_text("second", encoding="utf-8")
        target = restore(snapshot, tmp_path / "restored")
        with sqlite3.connect(target / "app.db") as connection:
            assert connection.execute("SELECT number FROM orders").fetchone()[0] == "A-1"
        assert (target / "storage_data" / "drawing.txt").read_text(encoding="utf-8") == "first"
        (snapshot / "storage" / "drawing.txt").write_text("corrupt", encoding="utf-8")
        with pytest.raises(RuntimeError, match="checksum"):
            verify(snapshot)
        with pytest.raises(RuntimeError, match="checksum"):
            status(tmp_path / "backups")
    finally:
        settings.database_url, settings.local_storage_path, settings.backup_mirror_path = original_db, original_storage, original_mirror


def _order_with_parts(client, auth_headers, db_session):
    order_id = uuid.UUID(_order(client, auth_headers))
    material = db_session.scalar(select(Material))
    edge = db_session.scalar(select(EdgeMaterial))
    item = OrderItem(order_id=order_id, item_type="custom", name="Door",
                     width=Decimal("1000"), height=Decimal("500"), depth=Decimal("16"),
                     quantity=2, material_id=material.id)
    db_session.add(item)
    db_session.flush()
    part = Part(order_id=order_id, order_item_id=item.id, part_code="door-a", name="Door",
                length=Decimal("1000"), width=Decimal("500"), thickness=Decimal("16"),
                quantity=2, material_id=material.id)
    db_session.add(part)
    db_session.flush()
    db_session.add(PartEdge(part_id=part.id, side="left", edge_material_id=edge.id,
                            length_mm=Decimal("1000")))
    db_session.commit()
    return order_id, material.id, edge.id


def test_stock_receipt_reserve_writeoff_is_idempotent(client, auth_headers, db_session):
    order_id, material_id, edge_id = _order_with_parts(client, auth_headers, db_session)
    for kind, material, quantity in (("material", material_id, "2"),
                                     ("edge_material", edge_id, "5")):
        response = client.post("/api/v1/stock/receipts", json={
            "material_type": kind, "material_id": str(material), "quantity": quantity,
        }, headers=auth_headers)
        assert response.status_code == 200, response.text
    for action in ("reserve-stock", "reserve-stock", "writeoff-stock", "writeoff-stock"):
        response = client.post(f"/api/v1/orders/{order_id}/{action}", headers=auth_headers)
        assert response.status_code == 200, response.text
    rows = db_session.scalars(select(StockItem)).all()
    by_kind = {row.material_type: row for row in rows}
    assert by_kind["material"].quantity == Decimal("1.000")
    assert by_kind["material"].reserved_quantity == Decimal("0.000")
    assert by_kind["edge_material"].quantity == Decimal("3.000")
    assert by_kind["edge_material"].reserved_quantity == Decimal("0.000")
    movements = db_session.scalars(select(StockMovement)).all()
    assert len(movements) == 6
    assert {row.movement_type for row in movements} == {"receipt", "reserve", "writeoff"}


def test_stock_reserve_rejects_shortage_without_partial_change(client, auth_headers, db_session):
    order_id, material_id, edge_id = _order_with_parts(client, auth_headers, db_session)
    for kind, material, quantity in (("material", material_id, "2"),
                                     ("edge_material", edge_id, "1")):
        response = client.post("/api/v1/stock/receipts", json={
            "material_type": kind, "material_id": str(material), "quantity": quantity,
        }, headers=auth_headers)
        assert response.status_code == 200, response.text
    response = client.post(f"/api/v1/orders/{order_id}/reserve-stock", headers=auth_headers)
    assert response.status_code == 422, response.text
    assert db_session.scalar(select(StockItem).where(StockItem.material_type == "material")).reserved_quantity == 0
    assert db_session.scalars(select(StockMovement).where(StockMovement.movement_type == "reserve")).all() == []


def test_reseeding_cannot_restore_demo_password_or_reactivate_user(db_session):
    user = db_session.scalar(select(User).where(User.login == "admin"))
    original_hash = user.password_hash
    user.is_active = False
    db_session.commit()
    upsert_user(db_session, "admin", "Reset Name", "reset@example.invalid", "admin", "admin123")
    db_session.commit()
    db_session.refresh(user)
    assert user.password_hash == original_hash
    assert user.is_active is False
    assert user.full_name != "Reset Name"


def test_cnc_machine_can_be_selected_but_export_remains_preview(
    client, auth_headers, manager_auth_headers, db_session, tmp_path: Path, monkeypatch,
):
    from app.modules.cnc import service as cnc_service
    from app.storage.local import LocalStorageBackend

    order_id, _, _ = _order_with_parts(client, auth_headers, db_session)
    monkeypatch.setattr(cnc_service, "get_storage_backend", lambda: LocalStorageBackend(tmp_path))
    created = client.post("/api/v1/cnc/machines", json={
        "name": "Router A", "controller": "Controller X",
    }, headers=auth_headers)
    assert created.status_code == 200, created.text
    machine_id = created.json()["data"]["id"]
    assert client.get("/api/v1/cnc/machines", headers=auth_headers).json()["data"][0]["id"] == machine_id
    assert client.post("/api/v1/cnc/machines", json={"name": "Router A"},
                       headers=auth_headers).status_code == 409
    assert client.post("/api/v1/cnc/machines", json={"name": "Manager Router"},
                       headers=manager_auth_headers).status_code == 403

    response = client.post(f"/api/v1/orders/{order_id}/generate-cnc",
                           json={"machine_id": machine_id}, headers=auth_headers)
    assert response.status_code == 200, response.text
    job = response.json()["data"][0]
    assert job["machine_id"] == machine_id
    assert job["machine_name"] == "Router A"
    assert job["postprocessor"] == "mock_text_v1"
    assert job["file_name"].endswith(".preview.txt")
    assert "NOT A MACHINE PROGRAM" in (tmp_path / job["file_path"]).read_text(encoding="utf-8")

    disabled = client.patch(f"/api/v1/cnc/machines/{machine_id}",
                            json={"is_active": False}, headers=auth_headers)
    assert disabled.status_code == 200, disabled.text
    refused = client.post(f"/api/v1/orders/{order_id}/generate-cnc",
                          json={"machine_id": machine_id}, headers=auth_headers)
    assert refused.status_code == 422, refused.text


def test_facade_order_can_make_machine_specific_preview_without_catalog_parts(
    client, auth_headers, tmp_path: Path, monkeypatch,
):
    from app.modules.cnc import service as cnc_service
    from app.storage.local import LocalStorageBackend

    order_id = _order(client, auth_headers)
    positions = client.put(f"/api/v1/orders/{order_id}/positions", json={"positions": [
        {"name": "White soft", "is_custom": True, "unit_price": "1200", "quantity": "2",
         "width": "1000", "height": "500", "article": "110", "milling": "Art. 110",
         "color": "White soft", "thickness": "16"},
    ]}, headers=auth_headers)
    assert positions.status_code == 200, positions.text
    machine = client.post("/api/v1/cnc/machines", json={"name": "Demo router"},
                          headers=auth_headers).json()["data"]
    monkeypatch.setattr(cnc_service, "get_storage_backend", lambda: LocalStorageBackend(tmp_path))
    response = client.post(f"/api/v1/orders/{order_id}/generate-cnc",
                           json={"machine_id": machine["id"]}, headers=auth_headers)
    assert response.status_code == 200, response.text
    job = response.json()["data"][0]
    assert job["part_id"] is None
    assert job["machine_id"] == machine["id"]
    preview = (tmp_path / job["file_path"]).read_text(encoding="utf-8")
    assert "Milling: Art. 110" in preview
    assert "NOT A MACHINE PROGRAM" in preview
