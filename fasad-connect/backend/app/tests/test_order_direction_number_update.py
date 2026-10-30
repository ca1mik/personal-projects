from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.modules.directions.models import ProductionDirection
from app.modules.directions.service import DirectionService
from app.modules.orders.models import Order


@pytest.mark.parametrize("number,suffix,expected", [
    ("0003", "П", "0003-П"), ("0003-П", "Ш", "0003-Ш"),
    ("0003-Ш", "", "0003"), ("3476-Ф", "", "3476"),
    ("44 03-П/12", "Ш", "44 03-Ш/12"), ("44-03/1", "П", "44-03-П/1"),
    ("3476П", "", "3476"), ("0003-П/2", "П", "0003-П/2"),
])
def test_only_direction_suffix_changes(number, suffix, expected):
    assert DirectionService.change_order_number_direction(number, SimpleNamespace(number_suffix=suffix)) == expected


@pytest.fixture
def number_directions(db_session):
    rows = [ProductionDirection(code=code, name=name, number_suffix=suffix)
            for code, name, suffix in [("enamel", "Эмаль", ""), ("pvc", "ПВХ", "П"), ("veneer", "Шпон", "Ш")]]
    db_session.add_all(rows); db_session.commit()
    return {row.code: row for row in rows}


def make_order(client, auth_headers, number, direction="enamel"):
    lead = client.post('/api/v1/leads/intake', json={
        'source_channel': 'manual_manager_input', 'text': f'Номер {number}',
        'sender': {'full_name': 'Тест номера', 'email': f'{number.replace("/", "-")}@example.com'},
        'direction_code': direction,
    }).json()['data']
    response = client.post(f'/api/v1/leads/{lead["id"]}/create-order', headers=auth_headers, json={'order_number': number})
    assert response.status_code == 200, response.text
    return response.json()['data']


def test_direction_switch_updates_number_for_code_and_id(client, auth_headers, number_directions):
    order = make_order(client, auth_headers, '004403')
    for payload, expected in [({'direction_code': 'pvc'}, '004403-П'),
                              ({'direction_id': str(number_directions['veneer'].id)}, '004403-Ш'),
                              ({'direction_code': 'enamel'}, '004403')]:
        response = client.patch(f'/api/v1/orders/{order["id"]}', headers=auth_headers, json=payload)
        assert response.status_code == 200, response.text
        assert response.json()['data']['order_number'] == expected
        assert response.json()['data']['id'] == order['id']


def test_number_conflict_leaves_direction_and_number_unchanged(client, auth_headers, number_directions):
    order = make_order(client, auth_headers, '3476')
    make_order(client, auth_headers, '3476', 'pvc')
    response = client.patch(f'/api/v1/orders/{order["id"]}', headers=auth_headers, json={'direction_code': 'pvc'})
    assert response.status_code == 409, response.text
    saved = client.get(f'/api/v1/orders/{order["id"]}', headers=auth_headers).json()['data']
    assert saved['order_number'] == '3476'
    assert saved['direction']['code'] == 'enamel'


def test_additional_number_keeps_numeric_tail(client, auth_headers, db_session, number_directions):
    order = make_order(client, auth_headers, '004403')
    saved = db_session.scalar(select(Order).where(Order.order_number == '004403'))
    saved.order_number = '004403-Ф/2'
    db_session.commit()
    response = client.patch(f'/api/v1/orders/{order["id"]}', headers=auth_headers, json={'direction_code': 'pvc'})
    assert response.status_code == 200, response.text
    assert response.json()['data']['order_number'] == '004403-П/2'
