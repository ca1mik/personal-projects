import uuid

import pytest
from sqlalchemy import select

from app.modules.audit.models import AuditLog
from app.modules.directions.models import ProductionDirection
from app.modules.shared.numbering import peek
from app.tests.test_order_lifecycle_trash import make_order


def test_rename_keeps_order_and_audit_and_reserves_sequence(client, auth_headers, db_session):
    _, first = make_order(client, auth_headers, '0003')
    path = '/api/v1/orders/' + first['id']
    response = client.patch(path, json={'order_number': ' 003476 '}, headers=auth_headers)
    assert response.status_code == 200, response.text
    saved = response.json()['data']
    assert saved['id'] == first['id'] and saved['client_id'] == first['client_id']
    assert saved['order_number'] == '003476'
    assert saved['final_amount'] == first['final_amount']
    rows = client.get('/api/v1/orders?search=003476', headers=auth_headers).json()['data']
    assert [row['id'] for row in rows] == [first['id']]
    event = db_session.scalars(select(AuditLog).where(AuditLog.action == 'update_order', AuditLog.entity_id == first['id'])).all()[-1]
    assert event.old_value_json['order_number'] == '0003'
    assert event.new_value_json['order_number'] == '003476'
    assert peek(db_session, 'orders') == 3477
    assert client.patch(path, json={'order_number': '2'}, headers=auth_headers).status_code == 200
    assert peek(db_session, 'orders') == 3477


@pytest.mark.parametrize('value', ['', '  ', None, '1\n2', '1\t2', '1'*51, '9'*50])
def test_invalid_number_does_not_change_order(client, auth_headers, value):
    _, first = make_order(client, auth_headers, '0003')
    path = '/api/v1/orders/' + first['id']
    result = client.patch(path, json={'order_number': value}, headers=auth_headers)
    assert result.status_code == 422, result.text
    assert client.get(path, headers=auth_headers).json()['data']['order_number'] == '0003'


def test_conflict_including_trash_and_permissions(client, auth_headers, operator_auth_headers):
    _, first = make_order(client, auth_headers, '0003')
    _, second = make_order(client, auth_headers, '3476')
    path = '/api/v1/orders/' + first['id']
    assert client.patch(path, json={'order_number':'3476'}, headers=operator_auth_headers).status_code == 403
    assert client.delete('/api/v1/orders/' + second['id'], headers=auth_headers).status_code == 200
    assert client.patch(path, json={'order_number':'3476','comment':'must rollback'}, headers=auth_headers).status_code == 409
    saved = client.get(path, headers=auth_headers).json()['data']
    assert saved['order_number'] == '0003' and saved['comment'] == first['comment']
    assert client.delete(path, headers=auth_headers).status_code == 200
    assert client.patch(path, json={'order_number':'4000'}, headers=auth_headers).status_code == 404


def test_rename_honors_direction_and_same_request_direction_change(client, auth_headers, db_session):
    for code, suffix in [('pvc','П'), ('enamel','')]:
        db_session.add(ProductionDirection(code=code, name=code, number_suffix=suffix))
    db_session.commit()
    _, first = make_order(client, auth_headers, '0003')
    path = '/api/v1/orders/' + first['id']
    for payload, expected in [({'order_number':'0044','direction_code':'pvc'},'0044-П'),
                              ({'order_number':'0055-Ш'},'0055-П'),
                              ({'order_number':'0066-П','direction_code':'enamel'},'0066'),
                              ({'order_number':'44 03-П/2'},'44 03/2')]:
        result = client.patch(path, json=payload, headers=auth_headers)
        assert result.status_code == 200, result.text
        assert result.json()['data']['order_number'] == expected
