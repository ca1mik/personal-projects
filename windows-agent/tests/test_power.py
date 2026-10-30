import asyncio,json,time
import pytest
from localagent.base import Store
from localagent.service import Service

class Bot:
    def __init__(self):self.calls=[]
    async def call(self,method,**payload):self.calls.append((method,payload));return True

@pytest.fixture
def env(tmp_path,monkeypatch):
    s=Store(tmp_path/'test.sqlite3');s.put('owner',123);s.put('owner_chat',123)
    svc=Service(s,Bot());calls=[]
    async def run(args):calls.append(args);return {'code':0,'detail':''}
    monkeypatch.setattr(svc.power,'run',run)
    return svc,s,calls

def msg(text,uid=1,user=123):return {'update_id':uid,'message':{'from':{'id':user},'chat':{'id':user,'type':'private'},'text':text}}

@pytest.mark.parametrize('text,flag',[('/shutdown','/s'),('/reboot','/r'),('выключи компьютер','/s'),('перезагрузи пк','/r')])
def test_power_commands_execute_fixed_local_action(env,text,flag):
    svc,s,calls=env;asyncio.run(svc.handle(msg(text)))
    assert len(calls)==1 and calls[0][:3]==[flag,'/t','60']
    assert not svc.closing and not s.kv('paused',False)
    assert 58<s.kv('pc_power_pending')['due']-time.time()<61
    assert '/cancelshutdown' in s.rows('SELECT payload FROM outbox')[0]['payload']

def test_repeat_update_cannot_reschedule_shutdown(env):
    svc,s,calls=env
    asyncio.run(svc.handle(msg('/shutdown')));asyncio.run(svc.handle(msg('/shutdown')))
    assert len(calls)==1

@pytest.mark.parametrize('text',['/shutdown 0','/shutdown 999999','/shutdown 60 /f','/reboot 5','/reboot ;whoami'])
def test_reject_unsafe_power_arguments(env,text):
    svc,s,calls=env;asyncio.run(svc.handle(msg(text)));assert calls==[]

def test_cancel_is_local_and_available_on_pause(env):
    svc,s,calls=env;s.put('paused',True)
    asyncio.run(svc.handle(msg('/cancelshutdown')))
    assert calls==[['/a']] and s.kv('pc_power_pending') is None

def test_power_probe_cancels_each_action(env):
    svc,s,calls=env;asyncio.run(svc.handle(msg('/power_test')))
    assert [a[0] for a in calls]==['/s','/a','/r','/a']
    assert s.kv('pc_power_test')['results']==[{'action':'/s','schedule':0,'abort':0},{'action':'/r','schedule':0,'abort':0}]

def test_probe_does_not_cancel_somebody_elses_shutdown(env,monkeypatch):
    svc,s,calls=env
    async def rejected(args):calls.append(args);return {'code':1190,'detail':'already pending'}
    monkeypatch.setattr(svc.power,'run',rejected)
    asyncio.run(svc.handle(msg('/power_test')))
    assert len(calls)==1 and calls[0][0]=='/s'

@pytest.mark.parametrize('text',['/shutdown','/reboot','/power_test','/cancelshutdown'])
def test_outsider_cannot_control_power(env,text):
    svc,s,calls=env;asyncio.run(svc.handle(msg(text,user=999)));assert not calls

def test_owner_buttons_control_only_known_actions(env):
    svc,s,calls=env
    update={'callback_query':{'id':'x','from':{'id':123},'data':'power:shutdown','message':{'message_id':11,'chat':{'id':123,'type':'private'}}}}
    asyncio.run(svc.handle(update));assert calls[0][0]=='/s'
    update['callback_query']['id']='y';update['callback_query']['from']['id']=999
    asyncio.run(svc.handle(update));assert len(calls)==1

def test_failed_os_command_never_reported_scheduled(env,monkeypatch):
    svc,s,calls=env
    async def denied(args):return {'code':5,'detail':'access denied'}
    monkeypatch.setattr(svc.power,'run',denied)
    asyncio.run(svc.handle(msg('/shutdown')))
    assert not s.kv('pc_power_pending') and 'код 5' in json.loads(s.rows('SELECT payload FROM outbox')[0]['payload'])['text']
