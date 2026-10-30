import json
import httpx
import pytest
from connect.store import Store
from connect.crm import Bitrix,DemoBitrix,CrmError,synchronize,validate_webhook,scope_for


@pytest.fixture
def local(tmp_path):return Store(tmp_path)


@pytest.fixture
def order():return {'id':'order-a','number':'1041-П','client':'Кухни Север','amount':'10245.50','status':'Новый','status_code':'new','positions':[{'width':'450','height':'720','quantity':'8'}]}


def counts(s):
    with s.db() as db:return tuple(db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('demo_deals','demo_comments'))


def test_repeated_sync_updates_same_deal_and_does_not_duplicate_document(local,order):
    a=synchronize(local,order,b'xlsx-one','quote.xlsx')
    b=synchronize(local,order,b'xlsx-two-different-zip-timestamps','quote.xlsx')
    assert a['deal_id']==b['deal_id']
    assert counts(local)==(1,1)


def test_changed_amount_updates_deal_and_versions_document(local,order):
    first=synchronize(local,order,b'x','quote.xlsx')
    order['amount']='24000.00';order['status']='В производстве'
    again=synchronize(local,order,b'y','quote.xlsx')
    deal=DemoBitrix(local).call('crm.deal.get',{'id':first['deal_id']})['result']
    assert deal['OPPORTUNITY']=='24000.00'
    assert first['deal_id']==again['deal_id']
    assert counts(local)==(1,2)


class LostAdd(DemoBitrix):
    def __init__(self,s):super().__init__(s);self.lost=True;self.calls=0
    def call(self,method,payload=None):
        result=super().call(method,payload)
        if method=='crm.deal.add':
            self.calls+=1
            if self.lost:self.lost=False;raise CrmError('Ответ потерян',uncertain=True)
        return result


def test_lost_add_response_recovers_by_external_id(local,order):
    remote=LostAdd(local)
    with pytest.raises(CrmError):synchronize(local,order,b'x','quote.xlsx',adapter=remote)
    result=synchronize(local,order,b'x','quote.xlsx',adapter=remote)
    assert result['state']=='synced'
    assert remote.calls==1
    assert counts(local)==(1,1)


class FailedAdd(DemoBitrix):
    calls=0
    def call(self,method,payload=None):
        if method=='crm.deal.add':self.calls+=1;raise CrmError('Не подтверждено',uncertain=True)
        return super().call(method,payload)


def test_uncertain_add_is_never_blindly_repeated(local,order):
    remote=FailedAdd(local)
    for _ in range(3):
        with pytest.raises(CrmError):synchronize(local,order,b'x','quote.xlsx',adapter=remote)
    assert remote.calls==1
    assert counts(local)==(0,0)


class LostDocument(DemoBitrix):
    lost=True
    def call(self,method,payload=None):
        result=super().call(method,payload)
        if method=='crm.timeline.comment.add' and self.lost:self.lost=False;raise CrmError('Ответ потерян',uncertain=True)
        return result


def test_lost_document_response_is_reconciled_not_duplicated(local,order):
    remote=LostDocument(local)
    with pytest.raises(CrmError):synchronize(local,order,b'x','quote.xlsx',adapter=remote)
    synchronize(local,order,b'x','quote.xlsx',adapter=remote)
    assert counts(local)==(1,1)


def test_attach_existing_deal_keeps_title_and_does_not_create_another(local,order):
    remote=DemoBitrix(local)
    deal=remote.call('crm.deal.add',{'fields':{'TITLE':'Исходная сделка','OPPORTUNITY':'1'}})['result']
    result=synchronize(local,order,b'x','quote.xlsx',existing_id=deal)
    stored=remote.call('crm.deal.get',{'id':deal})['result']
    assert result['deal_id']==deal
    assert stored['TITLE']=='Исходная сделка'
    assert stored['OPPORTUNITY']==order['amount']
    assert counts(local)==(1,1)


def test_cannot_relink_existing_order(local,order):
    synchronize(local,order,b'x','quote.xlsx')
    with pytest.raises(CrmError,match='другой сделкой'):synchronize(local,order,b'x','quote.xlsx',existing_id=999)


def test_deal_owned_by_other_order_cannot_be_bound(local,order):
    remote=DemoBitrix(local)
    deal=remote.call('crm.deal.add',{'fields':{'TITLE':'Other','ORIGINATOR_ID':'FASAD_CONNECT_'+local.get('instance_id'),'ORIGIN_ID':'other-order'}})['result']
    with pytest.raises(CrmError,match='другому заказу'):synchronize(local,order,b'x','quote.xlsx',existing_id=deal)


def test_status_mapping_is_opt_in(local,order):
    remote=DemoBitrix(local)
    result=synchronize(local,order,b'x','quote.xlsx')
    assert 'STAGE_ID' not in remote.call('crm.deal.get',{'id':result['deal_id']})['result']
    c=local.config();c.update(stage_map={'new':'C2:NEW'},status_field='UF_CRM_STATUS');local.set('config',c)
    synchronize(local,order,b'x','quote.xlsx')
    fields=remote.call('crm.deal.get',{'id':result['deal_id']})['result']
    assert fields['STAGE_ID']=='C2:NEW'
    assert fields['UF_CRM_STATUS']=='Новый'


@pytest.mark.parametrize('url',['http://a.bitrix24.ru/rest/1/key/','https://localhost/rest/1/key/','https://a.bitrix24.ru.evil.com/rest/1/key/','https://a.bitrix24.ru@evil.com/rest/1/key/','https://127.0.0.1/rest/1/key/','https://a.bitrix24.ru/rest/1/key/?next=x','https://a.bitrix24.ru/rest/1/key/crm.deal.add'])
def test_webhook_rejects_unsafe_or_wrong_urls(url):
    with pytest.raises(ValueError):validate_webhook(url)


def test_webhook_secret_is_encrypted(local):
    secret='https://shop.bitrix24.ru/rest/1/secretTokenABC/'
    local.save_webhook(secret)
    assert local.webhook()==secret
    assert b'secretTokenABC' not in local.path.read_bytes()


def test_http_errors_do_not_leak_webhook_key():
    def fail(request):raise httpx.ConnectError(str(request.url),request=request)
    crm=Bitrix('https://shop.bitrix24.ru/rest/1/SECRET123/',transport=httpx.MockTransport(fail))
    with pytest.raises(CrmError) as error:crm.call('crm.deal.add')
    assert 'SECRET123' not in str(error.value)


def test_remote_error_description_is_not_echoed():
    crm=Bitrix('https://shop.bitrix24.ru/rest/1/SECRET123/',transport=httpx.MockTransport(lambda _:httpx.Response(200,json={'error':'ACCESS_DENIED','error_description':'SECRET123'})))
    with pytest.raises(CrmError) as error:crm.call('crm.deal.fields')
    assert str(error.value)=='Битрикс24 отклонил запрос: ACCESS_DENIED'


def test_portal_scope_separates_demo_and_real_links():
    assert scope_for({'mode':'demo'},'')!=scope_for({'mode':'bitrix'},'https://shop.bitrix24.ru/rest/1/a/')
    assert scope_for({'mode':'bitrix'},'https://shop.bitrix24.ru/rest/1/a/')==scope_for({'mode':'bitrix'},'https://shop.bitrix24.ru/rest/2/b/')


def test_bitrix_sends_documented_json_parameters(order):
    calls=[]
    def handler(request):
        calls.append((request.url.path,json.loads(request.content)))
        return httpx.Response(200,json={'result':12})
    crm=Bitrix('https://shop.bitrix24.ru/rest/1/key/',transport=httpx.MockTransport(handler))
    assert crm.call('crm.timeline.comment.add',{'fields':{'ENTITY_ID':12,'ENTITY_TYPE':'deal','COMMENT':'test','FILES':[['quote.xlsx','eA==']]}})['result']==12
    assert calls[0][0].endswith('/crm.timeline.comment.add.json')
    assert 'fields' in calls[0][1]


def test_explicit_rejection_can_be_retried_after_fix(local,order):
    class Denied(DemoBitrix):
        denied=True
        def call(self,method,payload=None):
            if method=='crm.deal.add' and self.denied:self.denied=False;raise CrmError('ACCESS_DENIED')
            return super().call(method,payload)
    remote=Denied(local)
    with pytest.raises(CrmError):synchronize(local,order,b'x','quote.xlsx',adapter=remote)
    synchronize(local,order,b'x','quote.xlsx',adapter=remote)
    assert counts(local)==(1,1)


def test_document_explicit_rejection_can_be_retried(local,order):
    class Denied(DemoBitrix):
        denied=True
        def call(self,method,payload=None):
            if method=='crm.timeline.comment.add' and self.denied:self.denied=False;raise CrmError('ACCESS_DENIED')
            return super().call(method,payload)
    remote=Denied(local)
    with pytest.raises(CrmError):synchronize(local,order,b'x','quote.xlsx',adapter=remote)
    synchronize(local,order,b'x','quote.xlsx',adapter=remote)
    assert counts(local)==(1,1)
