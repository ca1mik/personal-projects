import io

import pytest
from openpyxl import load_workbook
from sqlalchemy import func, select

from app.modules.directions.models import ProductionDirection
from app.modules.orders.models import Order


@pytest.fixture
def directions(db_session):
    for code, suffix in [('enamel', ''), ('pvc', 'П'), ('veneer', 'Ш')]:
        db_session.add(ProductionDirection(code=code, name=code, number_suffix=suffix))
    db_session.commit()


@pytest.mark.parametrize('direction,expected', [
    ('enamel', '003205 Доп'), ('pvc', '003205-П Доп'), ('veneer', '003205-Ш Доп'),
])
def test_shared_milling_supplement_is_one_independent_order_and_prints_full_number(
    client, auth_headers, db_session, directions, direction, expected
):
    result = client.post('/api/v1/leads/intake', json={
        'source_channel': 'manual_manager_input', 'lead_number': '003205 Доп',
        'direction_code': direction, 'text': 'Доп к старому заказу, которого нет в программе',
        'sender': {'full_name': 'Доп тест', 'phone': '+79990000009'},
        'raw_payload': {'parts': [
            {'length': '673', 'width': '230', 'quantity': '2', 'thickness': '16',
             'milling': 'МЫЛО R2', 'article': 'МЫЛО R2', 'kind': 'film'},
            {'length': '700', 'width': '400', 'quantity': '1', 'kind': 'paint'},
        ]},
    })
    assert result.status_code == 200, result.text
    lead = result.json()['data']
    response = client.post(f'/api/v1/leads/{lead["id"]}/create-order', json={}, headers=auth_headers)
    assert response.status_code == 200, response.text
    order = response.json()['data']
    assert order['order_number'] == expected
    saved = db_session.scalar(select(Order))
    assert saved.parent_order_id is None
    assert db_session.scalar(select(func.count()).select_from(Order)) == 1
    duplicate = client.post('/api/v1/orders', headers=auth_headers, json={
        'client_id': order['client_id'], 'manager_id': order['manager_id'],
        'order_number': '003205 Доп', 'direction_code': direction,
    })
    assert duplicate.status_code == 409, duplicate.text
    download = client.get(f'/api/v1/leads/{lead["id"]}/blank.xlsx?orderId={order["id"]}', headers=auth_headers)
    assert download.status_code == 200, download.text
    sheet = load_workbook(io.BytesIO(download.content)).active
    assert f'Бланк заказа: {expected}' in [c.value for row in sheet for c in row]
    for payload, number in [
        ({'direction_code': 'pvc'}, '003205-П Доп'),
        ({'direction_code': 'enamel'}, '003205 Доп'),
        ({'order_number': '004401 Доп'}, '004401 Доп'),
        ({'direction_code': 'veneer'}, '004401-Ш Доп'),
        ({'order_number': '004401'}, '004401-Ш'),
    ]:
        update = client.patch(f'/api/v1/orders/{order["id"]}', json=payload, headers=auth_headers)
        assert update.status_code == 200, update.text
        assert update.json()['data']['order_number'] == number
        assert update.json()['data']['id'] == order['id']


def test_supplement_marker_is_not_a_direction_letter_and_duplicate_is_rejected(
    client, auth_headers, db_session, directions
):
    from app.modules.directions.service import DirectionService
    from app.modules.orders.service import OrderService
    pvc = db_session.scalar(select(ProductionDirection).where(ProductionDirection.code == 'pvc'))
    assert DirectionService.change_order_number_direction('3205-П Доп', pvc) == '3205-П Доп'
    assert OrderService._resolve_order_number(db_session, '3205доп.', pvc, 'paint') == '3205-П Доп'
    assert DirectionService.change_order_number_direction('3205-П/1 Доп', None) == '3205/1 Доп'
