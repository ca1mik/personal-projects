from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4
import pytest

from sqlalchemy import select

from app.modules.cutting_export.models import Export
from app.modules.directions.models import ProductionDirection
from app.modules.orders.auto_film_layout import build_film_layout
from app.modules.orders.models import Order
from app.storage.factory import get_storage_backend


def _position(length, color="Белый", number=1):
    return SimpleNamespace(
        id=uuid4(), line_no=number, name=f"Фасад {number}",
        width=Decimal(length), height=Decimal("400"),
        quantity=Decimal("1"), color=color, milling="Мыло R2", thickness=Decimal("16"),
    )


def test_fixed_work_area_and_film_order_area():
    short = build_film_layout([_position("2450")])
    assert short.sheet_settings["sheetWidth"] == 3100
    assert short.sheet_settings["marginX"] == 150
    assert short.sheet_settings["marginRight"] == 200
    assert short.sheets[0]["workWidth"] == 2750
    assert short.sheets[0]["workHeight"] == 1170
    assert short.sheets[0]["orderedLength"] == 2800
    assert short.stats["rollAreaSqm"] == 3.64

    full = build_film_layout([_position("2500")])
    assert full.sheets[0]["orderedLength"] == 3100
    assert full.stats["rollAreaSqm"] == 4.03

    colors = build_film_layout([_position("500", "Белый"), _position("500", "Серый", 2)])
    assert len(colors.sheets) == 2
    assert {sheet["pattern"] for sheet in colors.sheets} == {"Белый", "Серый"}


def test_switching_to_enamel_saves_film_automatically(client, auth_headers, db_session):
    db_session.add(ProductionDirection(code="enamel", name="Эмаль", number_suffix=""))
    db_session.commit()
    lead = client.post("/api/v1/leads/intake", json={
        "source_channel": "website_form",
        "text": "Name: Enamel Test, phone +79991112233",
        "raw_payload": {"form_id": "auto-pvc-layout"},
    }).json()["data"]
    order = client.post(f"/api/v1/leads/{lead['id']}/create-order", headers=auth_headers, json={})
    assert order.status_code == 200, order.text
    order_id = order.json()["data"]["id"]
    order_uuid = UUID(order_id)
    positions = client.put(f"/api/v1/orders/{order_id}/positions", headers=auth_headers, json={
        "positions": [{"is_custom": True, "name": "Фасад", "quantity": "1", "width": "2450", "height": "400", "color": "Белый", "unit_price": "100"}],
    })
    assert positions.status_code == 200, positions.text
    # A saved MDF map must not be mistaken for an existing film map.
    mdf = client.post(f"/api/v1/orders/{order_id}/save-cutting-layout", headers=auth_headers, json={
        "sheet_settings": {"workKind": "cutting", "sheetWidth": 2800, "sheetHeight": 2070, "marginX": 8, "marginY": 8, "marginRight": 8, "marginBottom": 8, "defaultGapX": 4, "defaultGapY": 4},
        "stats": {}, "parts": [], "sheets": [{"width": 2800, "height": 2070, "placements": [{"unitId": "mdf-1", "x": 8, "y": 8, "width": 2450, "height": 400}]}],
    })
    assert mdf.status_code == 200, mdf.text
    # Direction is already set but the film snapshot is missing.
    saved_order = db_session.get(Order, order_uuid)
    saved_order.direction_id = db_session.scalar(select(ProductionDirection.id).where(ProductionDirection.code == "enamel"))
    db_session.commit()
    changed = client.patch(f"/api/v1/orders/{order_id}", headers=auth_headers, json={"direction_code": "enamel"})
    assert changed.status_code == 200, changed.text
    exports = list(db_session.scalars(select(Export).where(Export.order_id == order_uuid, Export.export_type == "cutting_layout")).all())
    assert len(exports) == 2
    snapshot = client.get(f"/api/v1/orders/{order_id}/cutting-layout/latest?work_kind=film", headers=auth_headers).json()["data"]
    assert snapshot["stats"]["source"] == "automatic_film"
    assert snapshot["sheets"][0]["orderedLength"] == 2800
    assert snapshot["stats"]["rollAreaSqm"] == 3.64

    changed_again = client.patch(f"/api/v1/orders/{order_id}", headers=auth_headers, json={"direction_code": "enamel"})
    assert changed_again.status_code == 200
    assert len(list(db_session.scalars(select(Export).where(Export.order_id == order_uuid, Export.export_type == "cutting_layout")).all())) == 2

    edited = client.put(f"/api/v1/orders/{order_id}/positions", headers=auth_headers, json={
        "positions": [{"is_custom": True, "name": "Фасад", "quantity": "1", "width": "2500", "height": "400", "color": "Белый", "unit_price": "100"}],
    })
    assert edited.status_code == 200, edited.text
    exports = list(db_session.scalars(select(Export).where(Export.order_id == order_uuid, Export.export_type == "cutting_layout").order_by(Export.version)).all())
    assert len(exports) == 3
    newest = json.loads(get_storage_backend().read_bytes(exports[-1].file_path))
    assert newest["sheets"][0]["orderedLength"] == 3100


@pytest.mark.parametrize("code,name,suffix", [("pvc", "ПВХ", "П"), ("veneer", "Шпон", "Ш"), ("other", "Другое", "")])
def test_other_directions_do_not_auto_save_film(client, auth_headers, db_session, code, name, suffix):
    db_session.add(ProductionDirection(code=code, name=name, number_suffix=suffix))
    db_session.commit()
    lead = client.post("/api/v1/leads/intake", json={"source_channel": "website_form", "text": "Name: Direction test, phone +79991112233", "raw_payload": {"form_id": code}}).json()["data"]
    order = client.post(f"/api/v1/leads/{lead['id']}/create-order", headers=auth_headers, json={}).json()["data"]
    order_id = order["id"]
    changed = client.patch(f"/api/v1/orders/{order_id}", headers=auth_headers, json={"direction_code": code})
    assert changed.status_code == 200, changed.text
    positions = client.put(f"/api/v1/orders/{order_id}/positions", headers=auth_headers, json={"positions": [{"is_custom": True, "name": "Фасад", "kind": "film", "quantity": "2", "width": "400", "height": "300", "unit_price": "100"}]})
    assert positions.status_code == 200, positions.text
    assert client.get(f"/api/v1/orders/{order_id}/cutting-layout/latest?work_kind=film", headers=auth_headers).json()["data"] is None


def test_ordered_film_length_rounds_up_to_tenth_metre():
    layout = build_film_layout([_position("1244")])
    assert layout.sheets[0]["orderedLength"] == 1600
    assert layout.stats["rollAreaSqm"] == 2.08
