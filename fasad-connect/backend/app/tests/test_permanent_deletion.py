import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select, text

from app.modules.audit.models import AuditLog
from app.modules.clients.models import Client
from app.modules.cutting_export.models import Export
from app.modules.documents.models import Document
from app.modules.leads.models import Lead
from app.modules.orders.models import Order, OrderItem, OrderPosition
from app.modules.parts_generator.models import Part, PartOperation
from app.modules.price_book.models import PriceItem, PriceItemChange
from app.modules.production.models import Material
from app.storage.local import LocalStorageBackend


def order(client, headers, number=None):
    lead = client.post('/api/v1/leads/intake', json={'source_channel': 'manual_manager_input', 'text': 'Name: Purge Test, phone +79991112233'}).json()['data']
    response = client.post(f"/api/v1/leads/{lead['id']}/create-order", json={'order_number': number}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()['data']


def trash(client, headers, item):
    result = client.delete(f"/api/v1/orders/{item['id']}", headers=headers)
    assert result.status_code == 200, result.text


def delete(client, headers, path, confirm=True):
    return client.request('DELETE', path, json={'confirm': confirm}, headers=headers)


def test_purge_requires_trash_confirmation_and_permission(client, auth_headers, operator_auth_headers):
    item = order(client, auth_headers)
    path = f"/api/v1/orders/{item['id']}/permanent"
    assert delete(client, auth_headers, path).status_code == 409
    trash(client, auth_headers, item)
    assert delete(client, auth_headers, path, False).status_code == 422
    assert client.delete(path, headers=auth_headers).status_code == 422
    for endpoint in (path, '/api/v1/orders/trash'):
        assert delete(client, operator_auth_headers, endpoint).status_code == 403
    assert delete(client, auth_headers, path).status_code == 200
    assert client.get(f"/api/v1/orders/{item['id']}", headers=auth_headers).status_code == 404
    assert client.post(f"/api/v1/orders/{item['id']}/restore", headers=auth_headers).status_code == 404


def test_purge_cleans_dependencies_files_but_keeps_client_lead_and_number(client, auth_headers, db_session, tmp_path, monkeypatch):
    from app.modules.orders import trash_service
    storage = LocalStorageBackend(tmp_path / 'storage')
    monkeypatch.setattr(trash_service, 'get_storage_backend', lambda: storage)
    item = order(client, auth_headers, '6000')
    identifier = uuid.UUID(item['id'])
    order_item = OrderItem(order_id=identifier, item_type='facade', name='Test', width=300, height=200, depth=16, quantity=1)
    db_session.add(order_item); db_session.flush()
    part = Part(order_id=identifier, order_item_id=order_item.id, part_code='ONE', name='Part', length=300, width=200, thickness=16,
                material_id=db_session.scalar(select(Material.id).limit(1)))
    db_session.add(part); db_session.flush()
    db_session.add(PartOperation(part_id=part.id, operation_type='drill'))
    for name, model in [('drawing.txt', Document), ('layout.json', Export)]:
        storage.save_text(name, 'test-only')
        values = dict(order_id=identifier, file_name=name, file_path=name)
        values.update(doc_type='attachment') if model is Document else values.update(export_type='cutting_layout', format='json')
        db_session.add(model(**values))
    db_session.commit()
    trash(client, auth_headers, item)
    result = delete(client, auth_headers, f"/api/v1/orders/{identifier}/permanent")
    assert result.status_code == 200, result.text
    assert db_session.scalar(select(Client.id).where(Client.id == uuid.UUID(item['client_id'])))
    assert db_session.scalar(select(Lead.id).where(Lead.id == uuid.UUID(item['source_lead_id'])))
    for model in (PartOperation, Part, OrderItem, Document, Export):
        assert db_session.scalar(select(func.count()).select_from(model)) == 0
    assert not list((tmp_path / 'storage').iterdir())
    assert db_session.scalar(select(AuditLog.id).where(AuditLog.action == 'purge_order'))
    assert db_session.execute(text('PRAGMA foreign_key_check')).all() == []
    assert order(client, auth_headers)['order_number'] == '6001'


def test_empty_trash_covers_more_than_one_page_and_keeps_active_orders(client, auth_headers, db_session):
    active = order(client, auth_headers)
    for index in range(103):
        db_session.add(Order(client_id=uuid.UUID(active['client_id']), manager_id=uuid.UUID(active['manager_id']),
                             status_id=uuid.UUID(active['status_id']), order_number=f'TRASH-{index}', deleted_at=datetime.now(UTC)))
    db_session.commit()
    response = delete(client, auth_headers, '/api/v1/orders/trash')
    assert response.status_code == 200, response.text
    assert response.json()['data']['deleted_count'] == 103
    assert [str(value) for value in db_session.scalars(select(Order.id))] == [active['id']]
    assert delete(client, auth_headers, '/api/v1/orders/trash').json()['data']['deleted_count'] == 0


def test_bulk_purge_is_atomic_when_stale_trash_has_payments(client, auth_headers, db_session):
    safe = order(client, auth_headers); trash(client, auth_headers, safe)
    paid = order(client, auth_headers)
    assert client.post(f"/api/v1/orders/{paid['id']}/payments", json={'amount': 10, 'method': 'cash'}, headers=auth_headers).status_code == 200
    stale = db_session.get(Order, uuid.UUID(paid['id'])); stale.deleted_at = datetime.now(UTC); db_session.commit()
    response = delete(client, auth_headers, '/api/v1/orders/trash')
    assert response.status_code == 409, response.text
    assert db_session.scalar(select(func.count()).select_from(Order)) == 2


def test_parent_and_child_can_be_purged_together(client, auth_headers, db_session):
    parent = order(client, auth_headers)
    response = client.post(f"/api/v1/orders/{parent['id']}/additional", json={}, headers=auth_headers)
    assert response.status_code == 200, response.text
    child = response.json()['data']
    trash(client, auth_headers, child); trash(client, auth_headers, parent)
    assert delete(client, auth_headers, f"/api/v1/orders/{parent['id']}/permanent").status_code == 409
    response = delete(client, auth_headers, '/api/v1/orders/trash')
    assert response.status_code == 200, response.text
    assert response.json()['data']['deleted_count'] == 2
    assert db_session.execute(text('PRAGMA foreign_key_check')).all() == []


def test_price_item_deletion_keeps_historical_order_values(client, auth_headers, operator_auth_headers, db_session):
    created = client.post('/api/v1/price-book', json={'article': 'DELETE-TEST', 'name': 'Test price', 'kind': 'other', 'unit': 'sqm', 'price': '100'}, headers=auth_headers)
    assert created.status_code == 200, created.text
    item = created.json()['data']
    saved = order(client, auth_headers)
    position = OrderPosition(order_id=uuid.UUID(saved['id']), line_no=1, price_item_id=uuid.UUID(item['id']), article='DELETE-TEST', name='Saved name', kind='other', unit='sqm', quantity=2,
                             area_sqm=2, unit_price=Decimal('100'), base_price=Decimal('100'), amount=Decimal('200'), width=1000, height=1000)
    db_session.add(position); db_session.commit()
    path = '/api/v1/price-book/' + item['id']
    assert delete(client, operator_auth_headers, path).status_code == 403
    assert delete(client, auth_headers, path, False).status_code == 422
    result = delete(client, auth_headers, path)
    assert result.status_code == 200, result.text
    assert client.get(path, headers=auth_headers).status_code == 404
    db_session.refresh(position)
    assert position.price_item_id is None
    assert (position.article, position.name, position.amount, position.unit_price, position.base_price, position.quantity) == ('DELETE-TEST', 'Saved name', Decimal('200'), Decimal('100'), Decimal('100'), 2)
    assert db_session.get(Order, uuid.UUID(saved['id'])).final_amount == Decimal(saved['final_amount'])
    assert db_session.scalar(select(func.count()).select_from(PriceItemChange).where(PriceItemChange.price_item_id == uuid.UUID(item['id']))) == 0
    assert db_session.execute(text('PRAGMA foreign_key_check')).all() == []
    assert client.post('/api/v1/price-book', json={'article': 'DELETE-TEST', 'name': 'New price', 'kind': 'other', 'unit': 'sqm', 'price': '150'}, headers=auth_headers).status_code == 200
