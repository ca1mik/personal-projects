from __future__ import annotations
import hashlib, html, json, re, time, asyncio
from collections import Counter
from urllib.parse import urlparse
import httpx
from .base import ROOT, get_secret, set_secret, config

class HH:
    def __init__(self, store):
        self.store=store
        self.refresh_lock=asyncio.Lock()
    async def refresh(self):
        async with self.refresh_lock:
            token=get_secret('hh_refresh')
            if not token:raise RuntimeError('Нужно повторно авторизовать hh.ru локально: manage.py hh-login')
            async with httpx.AsyncClient(timeout=30) as client:
                r=await client.post('https://api.hh.ru/token',data={'grant_type':'refresh_token','refresh_token':token})
            if r.status_code!=200:raise RuntimeError('Обновление hh.ru OAuth не удалось. Повторите manage.py hh-login локально.')
            obj=r.json();set_secret('hh_access',obj['access_token'])
            if obj.get('refresh_token'):set_secret('hh_refresh',obj['refresh_token'])
            self.store.put('hh_token_expires',time.time()+obj.get('expires_in',0))
    async def request(self, method, path, **kw):
        retried=kw.pop('_retried',False)
        url = path if path.startswith('https://') else 'https://api.hh.ru'+path
        if urlparse(url).hostname != 'api.hh.ru':
            raise ValueError('Unexpected HH API origin')
        headers={'HH-User-Agent':'PersonalWindowsAgent/1.0 (personal local job search)','User-Agent':'PersonalWindowsAgent/1.0'}
        token=get_secret('hh_access')
        expires=self.store.kv('hh_token_expires',0)
        if token and expires and expires<time.time()+60 and not retried:
            await self.refresh();token=get_secret('hh_access')
        if token:
            headers['Authorization']='Bearer '+token
        async with httpx.AsyncClient(timeout=35,follow_redirects=False) as client:
            r=await client.request(method,url,headers=headers,**kw)
        if r.status_code == 401:
            if not retried and get_secret('hh_refresh'):
                await self.refresh()
                return await self.request(method,path,_retried=True,**kw)
            raise RuntimeError('HH OAuth expired; run manage.py hh-login locally')
        if r.status_code in (403,429):
            raise RuntimeError(f'HH access restricted ({r.status_code}); automation paused, no CAPTCHA bypass. OAuth may be required.')
        if r.status_code>=400:
            raise RuntimeError(f'HH API HTTP {r.status_code}: '+r.text[:400])
        return r.json() if r.content else {}
    @staticmethod
    def assess(v):
        s=v.get('salary') or v.get('salary_range') or {}
        currency=s.get('currency')
        low,high=s.get('from'),s.get('to')
        salary = 'unknown'
        mode=s.get('mode') or {}
        if isinstance(mode,dict): mode=mode.get('id')
        if mode and mode not in ('MONTH','month'):
            salary='non_monthly_needs_review'
        elif currency=='RUR':
            salary='meets_floor' if low is not None and low>=80000 else 'possible_not_guaranteed' if high is not None and high>=80000 else 'below_floor' if high is not None and high<80000 else 'needs_review'
        formats=[x.get('id') for x in v.get('work_format',[])]
        office='ON_SITE' in formats
        remote_only=bool(formats) and all(x=='REMOTE' for x in formats)
        return {'salary_check':salary,'office_confirmed':office,'remote_only':remote_only,
                'gross':s.get('gross'),'formats':formats,'experience':v.get('experience'),
                'fit':'Нужен подтвержденный профиль опыта; вероятность приглашения не оценивалась'}
    async def search(self, query='IT OR CRM OR автоматизация OR техническая поддержка'):
        region=self.store.kv('hh_area')
        if not region:
            areas=await self.request('GET','/areas')
            def find(nodes):
                for n in nodes:
                    if n['name']=='Нижний Новгород': return n['id']
                    child=find(n.get('areas',[]))
                    if child: return child
            region=find(areas)
            if not region: raise RuntimeError('Nizhny Novgorod not found in HH areas')
            self.store.put('hh_area',region)
        result=await self.request('GET','/vacancies',params={'area':region,'salary':80000,'currency':'RUR',
            'label':'with_salary','text':query,'per_page':30,'order_by':'publication_time','period':14})
        ranked=[]
        for v in result.get('items',[]):
            assessment=self.assess(v)
            if assessment['salary_check']=='below_floor' or assessment['remote_only']: continue
            fp=hashlib.sha256((str((v.get('employer') or {}).get('id'))+'|'+v['name'].strip().lower()+'|'+region).encode()).hexdigest()
            repeats=self.store.rows('SELECT id FROM vacancies WHERE fingerprint=? AND id<>?',(fp,v['id']))
            existing=self.store.rows('SELECT id FROM vacancies WHERE id=?',(v['id'],))
            self.store.execute('INSERT INTO vacancies VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,last_seen=excluded.last_seen',
                (v['id'],fp,json.dumps(v,ensure_ascii=False),time.time(),time.time()))
            ranked.append({'id':v['id'],'title':v['name'],'employer':(v.get('employer') or {}).get('name'),
                'salary':v.get('salary') or v.get('salary_range'),'url':v['alternate_url'],
                'published':v.get('published_at'),'requirements':v.get('snippet'),**assessment,
                'possible_republication':bool(repeats),'new':not bool(existing)})
        ranked.sort(key=lambda v:(not v['office_confirmed'],v['salary_check']!='meets_floor'))
        report={'query':query,'area':region,'found_by_api':result.get('found'),'fetched':len(result.get('items',[])),
            'selected':ranked,'note':'Один запрос / максимум 30 свежих вакансий. Нижняя граница 80000 проверяется отдельно от верхней. Формат/налоги/опыт требуют проверки. Без OAuth HH может потребовать CAPTCHA; обхода нет.'}
        from .base import write_json
        path=ROOT/'artifacts'/('hh-'+str(time.time_ns())+'.json')
        write_json(path,report)
        report['artifact']=str(path)
        return report
    async def history(self):
        if not get_secret('hh_access'):
            return {'blocked':'Нужен OAuth hh.ru. Зарегистрируйте свое приложение на dev.hh.ru и выполните manage.py hh-login. Можно импортировать JSON/CSV историю локально.'}
        # API collection URLs are supplied by HH; never manufacture collection endpoints.
        data=await self.request('GET','/negotiations',params={'page':0,'per_page':50})
        containers=data.get('collections',[])
        items=list(data.get('items',[]))
        for page in range(1,data.get('pages',1)):
            chunk=await self.request('GET','/negotiations',params={'page':page,'per_page':50})
            items.extend(chunk.get('items',[]))
            await __import__('asyncio').sleep(.5)
        for collection in containers:
            if collection.get('url'):
                page=0
                while True:
                    chunk=await self.request('GET',collection['url'],params={'page':page,'per_page':50})
                    items.extend(chunk.get('items',[]))
                    page+=1
                    if page>=chunk.get('pages',1): break
                    await __import__('asyncio').sleep(.5)
        self.import_history(items)
        return self.statistics()
    def import_history(self,items):
        for row in items:
            vacancy=str((row.get('vacancy') or {}).get('id') or row.get('vacancy_id') or '')
            if not vacancy: continue
            state=row.get('state') or row.get('status') or 'unknown'
            if isinstance(state,dict): state=state.get('id','unknown')
            resume=row.get('resume') or row.get('resume_id') or ''
            if isinstance(resume,dict): resume=resume.get('id','')
            self.store.execute('INSERT OR REPLACE INTO applications VALUES(?,?,?,?,?)',
                (vacancy,str(resume),str(state),json.dumps(row,ensure_ascii=False),time.time()))
    def statistics(self):
        rows=self.store.rows('SELECT * FROM applications')
        counts=Counter(r['state'] for r in rows)
        n=len(rows)
        invited=sum(v for k,v in counts.items() if k in ('invitation','interview','offer'))
        rejected=sum(v for k,v in counts.items() if 'discard' in k or 'reject' in k)
        known_views=[json.loads(r['payload'])['viewed_by_opponent'] for r in rows if 'viewed_by_opponent' in json.loads(r['payload'])]
        viewed=sum(bool(v) for v in known_views)
        return {'total':n,'states':dict(counts),'invitation_rate':invited/n if n else None,
                'rejection_rate':rejected/n if n else None,'explicit_view_rate':viewed/len(known_views) if known_views else None,
                'explicit_view_sample':len(known_views),
                'causes':'Причины и автоматический характер отказов не установлены; время ответа само по себе не доказывает автоматический отказ.',
                'resume_breakdown':dict(Counter(r['resume'] for r in rows)),
                'source':'Только импортированная/доступная через OAuth история; полнота не гарантирована'}
    async def apply(self, **args):
        # The downloaded 2026-10-23 public spec does not publish applicant POST /negotiations.
        # Fail closed rather than assuming the legacy endpoint still works.
        return {'blocked':'Автоотклики пока отключены. Нужна OAuth-авторизация приложения hh.ru и проверка доступного метода apply-to-vacancy: официальная документация ссылается на него, но в загруженной public OpenAPI его описание отсутствует. Подготовьте письмо и откройте официальную страницу вакансии.'}
    async def reply(self,chat_id,text,key):
        if not get_secret('hh_access'): raise RuntimeError('HH OAuth required')
        if not re.fullmatch(r'[A-Za-z0-9_-]+',str(chat_id)): raise ValueError('Invalid chat id')
        return await self.request('POST',f'/common/chats/{chat_id}/messages',json={'text':text,'idempotency_key':key,'is_automated':True})
    async def messages(self,chat_id=None):
        if not get_secret('hh_access'):return {'blocked':'Для переписки нужна локальная OAuth-авторизация hh.ru.'}
        if chat_id:
            if not re.fullmatch(r'[A-Za-z0-9_-]+',str(chat_id)):raise ValueError('Invalid chat id')
            return await self.request('GET',f'/common/chats/{chat_id}/messages',params={'order':'prev','limit':20})
        return await self.request('GET','/common/chats',params={'page':0,'per_page':20,'filter_unread':'true'})
