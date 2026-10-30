from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import re
import socket
import threading
from urllib.parse import urlsplit

import httpx

from .store import Store


class CrmError(Exception):
    def __init__(self,message,uncertain=False):
        super().__init__(message)
        self.uncertain=uncertain


def validate_webhook(value):
    value=value.strip()
    u=urlsplit(value)
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.port not in (None,443):
        raise ValueError('Нужен HTTPS адрес входящего вебхука Битрикс24')
    if not re.fullmatch(r'[a-z0-9-]+\.(?:bitrix24\.(?:ru|com|by|kz|eu|de))',u.hostname):
        raise ValueError('В этой версии поддерживаются облачные порталы bitrix24.ru, .com, .by, .kz, .eu и .de')
    if not re.fullmatch(r'/rest/[1-9][0-9]*/[A-Za-z0-9_-]+/?',u.path):
        raise ValueError('Вставьте базовый адрес вида https://company.bitrix24.ru/rest/1/ключ/')
    return value.rstrip('/')+'/'


class Bitrix:
    def __init__(self, webhook, transport=None):
        self.webhook=validate_webhook(webhook)
        self.hostname=urlsplit(self.webhook).hostname
        self.transport=transport

    def call(self, method, payload=None):
        if not self.transport:
            try:
                addresses=socket.getaddrinfo(self.hostname,443,type=socket.SOCK_STREAM)
                if not addresses or any(not ipaddress.ip_address(x[4][0]).is_global for x in addresses):
                    raise CrmError('Адрес портала недоступен для подключения')
            except OSError:
                raise CrmError('Не удалось найти адрес портала') from None
        try:
            with httpx.Client(timeout=httpx.Timeout(25,connect=8),follow_redirects=False,trust_env=False,transport=self.transport) as client:
                response=client.post(self.webhook+method+'.json',json=payload or {})
                response.raise_for_status()
                data=response.json()
        except (httpx.HTTPError, ValueError):
            # Never log an exception containing the secret webhook URL.
            raise CrmError('CRM не подтвердила запрос. Проверьте соединение и повторите проверку связи.',uncertain=True) from None
        if not isinstance(data,dict):
            raise CrmError('CRM вернула ответ неизвестного формата',uncertain=True)
        if data.get('error'):
            code=re.sub('[^A-Za-z0-9_:-]','',str(data['error']))[:80]
            raise CrmError('Битрикс24 отклонил запрос: '+code)
        if 'result' not in data:
            raise CrmError('CRM не вернула результат операции',uncertain=True)
        return data


class DemoBitrix:
    def __init__(self, store: Store): self.store=store

    def call(self, method, payload=None):
        p=payload or {}
        with self.store.db() as db:
            if method=='crm.deal.fields':
                return {'result':{k:{} for k in ['TITLE','OPPORTUNITY','CURRENCY_ID','ORIGIN_ID','ORIGINATOR_ID','STAGE_ID']}}
            if method=='crm.deal.list':
                rows=db.execute('SELECT * FROM demo_deals').fetchall()
                result=[]
                for row in rows:
                    fields=json.loads(row['fields'])
                    if all(str(fields.get(k.lstrip('='),''))==str(v) for k,v in p.get('filter',{}).items()):
                        result.append({'ID':str(row['id']),**fields})
                return {'result':result}
            if method=='crm.deal.add':
                cursor=db.execute('INSERT INTO demo_deals(fields) VALUES (?)',(json.dumps(p['fields'],ensure_ascii=False),))
                return {'result':cursor.lastrowid}
            if method in ('crm.deal.get','crm.deal.update'):
                row=db.execute('SELECT * FROM demo_deals WHERE id=?',(int(p['id']),)).fetchone()
                if not row: raise CrmError('Сделка не найдена')
                fields=json.loads(row['fields'])
                if method.endswith('update'):
                    fields.update(p['fields'])
                    db.execute('UPDATE demo_deals SET fields=? WHERE id=?',(json.dumps(fields,ensure_ascii=False),p['id']))
                    return {'result':True}
                return {'result':{'ID':str(row['id']),**fields}}
            if method=='crm.timeline.comment.add':
                cursor=db.execute('INSERT INTO demo_comments(deal_id,fields) VALUES (?,?)',(int(p['fields']['ENTITY_ID']),json.dumps(p['fields'],ensure_ascii=False)))
                return {'result':cursor.lastrowid}
            if method=='crm.timeline.comment.list':
                deal=p['filter']['ENTITY_ID']
                rows=db.execute('SELECT * FROM demo_comments WHERE deal_id=? ORDER BY id DESC',(int(deal),)).fetchall()
                return {'result':[{'ID':str(r['id']),**json.loads(r['fields'])} for r in rows]}
            raise CrmError('Операция не поддерживается в демонстрации')


def scope_for(config, webhook):
    return 'demo' if config['mode']=='demo' else 'bitrix:'+str(urlsplit(webhook).hostname)


_sync_lock=threading.Lock()


def synchronize(store: Store, snapshot, document: bytes, filename: str, existing_id=None, adapter=None):
    if not _sync_lock.acquire(blocking=False):
        raise CrmError('Другая синхронизация уже выполняется. Повторите через несколько секунд.')
    try:
        config=store.config()
        webhook=store.webhook() if config['mode']=='bitrix' else ''
        if config['mode']=='bitrix' and not webhook:
            raise CrmError('Сначала сохраните вебхук в настройках подключения')
        scope=scope_for(config,webhook)
        crm=adapter or (DemoBitrix(store) if config['mode']=='demo' else Bitrix(webhook))
        oid=snapshot['id']
        link=store.link(scope,oid)
        origin='FASAD_CONNECT_'+store.get('instance_id')
        deal_id=link.get('deal_id') if link else None
        try:
            fields={'OPPORTUNITY':snapshot['amount'],'CURRENCY_ID':'RUB','IS_MANUAL_OPPORTUNITY':'Y'}
            if config.get('status_field'): fields[config['status_field']]=snapshot['status']
            if config.get('stage_map',{}).get(snapshot['status_code']): fields['STAGE_ID']=config['stage_map'][snapshot['status_code']]
            if existing_id:
                if deal_id and int(existing_id)!=int(deal_id):
                    raise CrmError('Заказ уже связан с другой сделкой. Изменение связи требует отдельной проверки.')
                remote=crm.call('crm.deal.get',{'id':int(existing_id)})['result']
                if remote.get('ORIGINATOR_ID')==origin and remote.get('ORIGIN_ID') not in (None,'',oid):
                    raise CrmError('Эта сделка уже относится к другому заказу Фасада')
                deal_id=int(existing_id)
                store.save_link(scope,oid,deal_id=deal_id,state='pending',error=None)
            if not deal_id:
                recovered=crm.call('crm.deal.list',{'filter':{'=ORIGINATOR_ID':origin,'=ORIGIN_ID':oid},'select':['ID'],'order':{'ID':'ASC'}})['result']
                if len(recovered)>1:
                    raise CrmError('Найдено несколько сделок этого заказа. Уточните связь вручную.')
                if recovered:
                    deal_id=int(recovered[0]['ID'])
                else:
                    # If a previous add timed out, do not issue another add on a retry.
                    if link and link['state']=='creating':
                        raise CrmError('Результат создания сделки пока не подтверждён. Проверьте CRM: новая сделка повторно не создаётся.',uncertain=True)
                    store.save_link(scope,oid,state='creating',error=None)
                    created={**fields,'TITLE':f"Фасад {snapshot['number']} · {snapshot['client']}",'ORIGINATOR_ID':origin,'ORIGIN_ID':oid}
                    raw_id=crm.call('crm.deal.add',{'fields':created,'params':{'REGISTER_SONET_EVENT':'N'}})['result']
                    if isinstance(raw_id,bool) or not str(raw_id).isdigit() or int(raw_id)<1:
                        raise CrmError('CRM не подтвердила номер созданной сделки',uncertain=True)
                    deal_id=int(raw_id)
                store.save_link(scope,oid,deal_id=deal_id,state='pending',error=None)
            if not crm.call('crm.deal.update',{'id':deal_id,'fields':fields})['result']:
                raise CrmError('CRM не подтвердила обновление сделки')
            base=config.get('public_url','').rstrip('/')
            order_url=base+'/orders/'+oid if base else ''
            # Use the canonical data, not XLSX bytes (ZIP timestamps are unstable).
            digest=hashlib.sha256(json.dumps({'snapshot':snapshot,'company':config.get('company'),'url':order_url},ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:24]
            marker='FC-'+digest
            publication=store.publication(scope,oid,digest)
            if not publication or publication['state']!='done':
                if publication and publication['state']=='sending':
                    found=[]
                    start=0
                    for _ in range(20):
                        batch=crm.call('crm.timeline.comment.list',{'filter':{'ENTITY_ID':deal_id,'ENTITY_TYPE':'deal'},'order':{'ID':'DESC'},'select':['ID','COMMENT'],'start':start})
                        found.extend(x for x in batch['result'] if marker in x.get('COMMENT',''))
                        if found or 'next' not in batch: break
                        start=batch['next']
                    if not found:
                        raise CrmError('Отправка документа пока не подтверждена. Проверьте историю сделки; повторный документ не отправлен.')
                    comment_id=int(found[0]['ID'])
                else:
                    comment=f"Заказ Фасад № {snapshot['number']}\nСтатус: {snapshot['status']}\nСумма: {snapshot['amount']} ₽\nДокумент расчёта: {marker}"
                    if order_url: comment+='\nЗаказ: '+order_url
                    store.save_publication(scope,oid,digest,'sending')
                    try:
                        comment_id=int(crm.call('crm.timeline.comment.add',{'fields':{'ENTITY_ID':deal_id,'ENTITY_TYPE':'deal','COMMENT':comment,'FILES':[[filename,base64.b64encode(document).decode()]]}})['result'])
                    except CrmError as error:
                        if not error.uncertain:store.save_publication(scope,oid,digest,'failed')
                        raise
                store.save_publication(scope,oid,digest,'done',comment_id)
            store.save_link(scope,oid,deal_id=deal_id,state='synced',error=None)
            store.event(oid,'success',f"Заказ {snapshot['number']} передан в {'тестовую CRM' if config['mode']=='demo' else 'Битрикс24'}, сделка № {deal_id}")
            return {'deal_id':deal_id,'mode':config['mode'],'scope':scope,'state':'synced','url':(f'https://{urlsplit(webhook).hostname}/crm/deal/details/{deal_id}/' if webhook else f'/connect?view=crm&deal={deal_id}')}
        except Exception as error:
            message=str(error) if isinstance(error,CrmError) else 'Не удалось сохранить результат синхронизации. Проверьте журнал и связь с CRM.'
            current=store.link(scope,oid)
            state='creating' if current and current['state']=='creating' and (not isinstance(error,CrmError) or error.uncertain) else 'error'
            store.save_link(scope,oid,state=state,error=message)
            store.event(oid,'error',message)
            raise CrmError(message) from None
    finally:
        _sync_lock.release()
