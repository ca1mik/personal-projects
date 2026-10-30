from __future__ import annotations
import pytest


@pytest.mark.parametrize('note',['Петли слева. Перед отгрузкой позвонить.','',None])
def test_order_information_and_customer_comment_are_separate(client,auth_headers,note):
    summary='Клиент: Студия\nТелефон: +79991112233\nРазмеры:\n720x400 — 3 шт.\nРасчёт: 10000 ₽'
    response=client.post('/api/v1/leads/intake',json={
        'source_channel':'manual_manager_input','lead_number':'004403',
        'text':summary,'sender':{'full_name':'Студия','email':'info-note@example.com'},
        'raw_payload':{'parts':[{'width':720,'height':400,'quantity':3}],'manual_note':note},
    })
    assert response.status_code==200,response.text
    lead=response.json()['data']
    created=client.post(f"/api/v1/leads/{lead['id']}/create-order",json={},headers=auth_headers)
    assert created.status_code==200,created.text
    order=created.json()['data']
    assert order['comment']==summary
    assert order['customer_comment']==(note or None)
    fetched=client.get(f"/api/v1/orders/{order['id']}",headers=auth_headers).json()['data']
    assert fetched['comment']==summary
    assert fetched['customer_comment']==(note or None)
    listing=client.get('/api/v1/orders',headers=auth_headers).json()['data']
    assert next(o for o in listing if o['id']==order['id'])['customer_comment']==(note or None)
