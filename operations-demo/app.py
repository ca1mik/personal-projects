from pathlib import Path
from contextlib import contextmanager
from datetime import date,datetime,timezone
from io import StringIO
import base64,csv,json,os,sqlite3
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import FileResponse,Response
from fastapi.staticfiles import StaticFiles
from domain import AREAS,FIELDS,parse_xlsx,summary,validate
from access import initialize,register,require_admin,require_edit,can_read,public
from workflow import register_workflow

ROOT=Path(__file__).resolve().parent
DEFAULT_DB=ROOT/'data'/'operations.sqlite3'

def create_app(db_path=None):
    db_path=Path(db_path or os.environ.get('OPERATIONS_DB',str(DEFAULT_DB)))
    db_path.parent.mkdir(parents=True,exist_ok=True)
    @contextmanager
    def db():
        c=sqlite3.connect(db_path,timeout=15);c.row_factory=sqlite3.Row
        try:
            with c:yield c
        finally:c.close()
    with db() as c:
        c.executescript('''PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY,area TEXT NOT NULL,payload TEXT NOT NULL,original TEXT NOT NULL,source_row INTEGER,revision INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,at TEXT NOT NULL,action TEXT NOT NULL,record INTEGER,before TEXT,after TEXT);
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
        ''')
        if 'deleted' not in {r[1] for r in c.execute('PRAGMA table_info(records)')}:
            c.execute('ALTER TABLE records ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0')
        for col in ('actor','area'):
            if col not in {r[1] for r in c.execute('PRAGMA table_info(audit)')}:
                c.execute(f"ALTER TABLE audit ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
        initialize(c)
    app=FastAPI(title='Контур · рабочие данные',docs_url='/api/docs')
    def read_rows(c):
        return [{'id':r['id'],'area':r['area'],'values':json.loads(r['payload']),'revision':r['revision'],'source_row':r['source_row']} for r in c.execute('SELECT * FROM records WHERE deleted=0 ORDER BY id')]
    def audit(c,action,ident,before,after,actor='',area=''):
        c.execute('INSERT INTO audit(at,action,record,before,after,actor,area) VALUES(?,?,?,?,?,?,?)',(datetime.now(timezone.utc).isoformat(),action,ident,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),actor,area))
    def actor(data):
        value=data.get('actor','')
        if not isinstance(value,str) or len(value)>80:raise HTTPException(422,'Имя автора должно быть короче 80 символов')
        return value.strip()
    async def body(request):
        raw=await request.body()
        if len(raw)>85*1024*1024:raise HTTPException(413,'Запрос слишком большой')
        try:
            value=json.loads(raw)
            if not isinstance(value,dict):raise ValueError()
            return value
        except (ValueError,TypeError):raise HTTPException(422,'Ожидается JSON-объект')
    def values(area,data):
        if area not in AREAS:raise HTTPException(404,'Неизвестный участок')
        if not isinstance(data,dict) or set(data)-set(FIELDS[area]):raise HTTPException(422,'Неизвестные поля')
        output={k:str(data.get(k,'' ) if data.get(k) is not None else '').strip() for k in FIELDS[area]}
        if any(len(v)>200 for v in output.values()):raise HTTPException(422,'Значение длиннее 200 символов')
        return output
    def report(c,start,end):
        try:
            date.fromisoformat(start);date.fromisoformat(end)
            if start>end:raise ValueError()
        except ValueError:raise HTTPException(422,'Проверьте начало и конец периода')
        return summary(read_rows(c),start,end)
    def scoped_report(c,request,start,end):
        checked=report(c,start,end)
        if request.state.user['role'] in ('admin','director'):return checked
        result=summary([r for r in read_rows(c) if can_read(request.state.user,r['area'])],start,end)
        result['totals']={a:t for a,t in result['totals'].items() if can_read(request.state.user,a)}
        return result
    @app.get('/api/state')
    def state(request:Request):
        with db() as c:
            rows=validate([r for r in read_rows(c) if can_read(request.state.user,r['area'])]);dates=sorted(r['values']['date'] for r in rows if 'Некорректная дата' not in r['issues'])
            return {'user':public(request.state.user),'initialized':bool(c.execute("SELECT value FROM meta WHERE key='imported'").fetchone()),'rows':rows,'areas':{a:n for a,n in AREAS.items() if can_read(request.state.user,a)},'fields':{a:f for a,f in FIELDS.items() if can_read(request.state.user,a)},
                    'min_date':dates[0] if dates else date.today().isoformat(),'max_date':dates[-1] if dates else date.today().isoformat(),
                    'version':c.execute('SELECT COALESCE(MAX(id),0) FROM audit').fetchone()[0]}
    @app.post('/api/import')
    async def import_files(request:Request):
        require_admin(request)
        data=await body(request);files=data.get('files',{})
        if not isinstance(files,dict) or set(files)!=set(AREAS):raise HTTPException(422,'Выберите все три файла')
        try:
            parsed={a:parse_xlsx(base64.b64decode(files[a],validate=True),a) for a in AREAS}
        except (ValueError,TypeError) as e:raise HTTPException(422,str(e))
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute("SELECT value FROM meta WHERE key='imported'").fetchone() or c.execute('SELECT 1 FROM records LIMIT 1').fetchone():raise HTTPException(409,'Первоначальный импорт уже выполнен. Исправляйте записи в системе.')
            for area,items in parsed.items():
                for r in items:
                    payload=json.dumps(r['values'],ensure_ascii=False)
                    c.execute('INSERT INTO records(area,payload,original,source_row) VALUES(?,?,?,?)',(area,payload,payload,r['source_row']))
            c.execute("INSERT INTO meta VALUES('imported',?)",(datetime.now(timezone.utc).isoformat(),));audit(c,'import',None,None,{a:len(rs) for a,rs in parsed.items()})
        return {'imported':{a:len(rs) for a,rs in parsed.items()}}
    @app.post('/api/records/{area}')
    async def add(area:str,request:Request):
        require_edit(request,area)
        data=await body(request);v=values(area,data.get('values'));who=request.state.user['username']
        with db() as c:
            if not c.execute("SELECT value FROM meta WHERE key='imported'").fetchone():raise HTTPException(409,'Сначала загрузите исходные файлы')
            payload=json.dumps(v,ensure_ascii=False)
            ident=c.execute('INSERT INTO records(area,payload,original) VALUES(?,?,?)',(area,payload,payload)).lastrowid
            audit(c,'create',ident,None,v,who,area)
        return {'id':ident}
    @app.put('/api/records/{area}/{ident}')
    async def edit(area:str,ident:int,request:Request):
        require_edit(request,area)
        data=await body(request);v=values(area,data.get('values'));who=request.state.user['username']
        with db() as c:
            c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT * FROM records WHERE id=? AND area=? AND deleted=0',(ident,area)).fetchone()
            if not r:raise HTTPException(404,'Запись не найдена')
            if data.get('revision')!=r['revision']:raise HTTPException(409,'Запись уже изменена в другом окне. Обновите экран.')
            c.execute('UPDATE records SET payload=?,revision=revision+1 WHERE id=?',(json.dumps(v,ensure_ascii=False),ident))
            audit(c,'edit',ident,json.loads(r['payload']),v,who,area)
        return {'saved':True}
    @app.delete('/api/records/{area}/{ident}')
    def remove(area:str,ident:int,revision:int,request:Request):
        require_edit(request,area);who=request.state.user['username']
        with db() as c:
            c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT * FROM records WHERE id=? AND area=? AND deleted=0',(ident,area)).fetchone()
            if not r:raise HTTPException(404,'Запись не найдена')
            if revision!=r['revision']:raise HTTPException(409,'Запись уже изменена. Обновите экран.')
            audit(c,'delete',ident,json.loads(r['payload']),None,who,area)
            c.execute('UPDATE records SET deleted=1,revision=revision+1 WHERE id=?',(ident,))
        return {'deleted':True}
    @app.post('/api/records/{area}/{ident}/restore')
    async def restore(area:str,ident:int,request:Request):
        require_edit(request,area);data=await body(request);who=request.state.user['username']
        with db() as c:
            c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT * FROM records WHERE id=? AND area=?',(ident,area)).fetchone()
            if not r:raise HTTPException(404,'Запись не найдена')
            if not r['deleted'] or data.get('revision')!=r['revision']:raise HTTPException(409,'Запись уже изменена. Обновите историю.')
            c.execute('UPDATE records SET deleted=0,revision=revision+1 WHERE id=?',(ident,))
            audit(c,'restore',ident,None,json.loads(r['payload']),who,area)
        return {'restored':True}
    @app.get('/api/history')
    def history(request:Request,area:str='',record:int|None=None,before:int|None=None):
        if area and area not in AREAS:raise HTTPException(422,'Неизвестный участок')
        if request.state.user['role'] not in ('admin','director'):
            if area and not can_read(request.state.user,area):raise HTTPException(403,'Нет доступа к истории другого участка')
            area=request.state.user['role']
        with db() as c:
            where=[];args=[]
            if area:where.append("COALESCE(NULLIF(a.area,''),r.area)=?");args.append(area)
            if record is not None:where.append('a.record=?');args.append(record)
            if before is not None:where.append('a.id<?');args.append(before)
            query='SELECT a.*,r.area AS current_area,r.deleted,r.revision FROM audit a LEFT JOIN records r ON r.id=a.record'
            if where:query+=' WHERE '+' AND '.join(where)
            rows=c.execute(query+' ORDER BY a.id DESC LIMIT 51',args).fetchall();items=[]
            for r in rows[:50]:
                old=json.loads(r['before']) if r['before'] else None;new=json.loads(r['after']) if r['after'] else None
                changes=[{'field':f,'before':(old or {}).get(f),'after':(new or {}).get(f)} for f in dict.fromkeys(list(old or {})+list(new or {})) if (old or {}).get(f)!=(new or {}).get(f)]
                items.append({'id':r['id'],'at':r['at'],'action':r['action'],'record':r['record'],'area':r['area'] or r['current_area'],
                              'actor':r['actor'] or 'Автор не указан','changes':changes,'label':(new or old or {}).get('record_id','Первоначальный импорт'),
                              'deleted':bool(r['deleted']),'revision':r['revision']})
            return {'items':items,'next_before':rows[49]['id'] if len(rows)>50 else None}
    @app.get('/api/report')
    def dashboard(request:Request,start:str,end:str):
        with db() as c:return scoped_report(c,request,start,end)
    @app.post('/api/preview/{area}')
    async def preview(area:str,request:Request,start:str,end:str):
        require_edit(request,area)
        data=await body(request);v=values(area,data.get('values'))
        with db() as c:
            previous=scoped_report(c,request,start,end);rows=[r for r in read_rows(c) if can_read(request.state.user,r['area'])]
            ident=data.get('id')
            current=next((r for r in rows if r['id']==ident and r['area']==area),None)
            if ident is not None and not current:raise HTTPException(404,'Запись не найдена')
            if current:current['values']=v
            else:
                ident=-1;rows.append({'id':ident,'area':area,'values':v,'revision':0,'source_row':None})
            checked=next(r for r in validate(rows) if r['id']==ident)
            after=summary(rows,start,end)
            return {'issues':checked['issues'],'before':previous['totals'],'after':after['totals'],
                    'batches':[b for b in after['batches'] if b['batch_id']==v.get('batch_id')]}
    @app.get('/api/export')
    def export(request:Request,start:str,end:str):
        with db() as c:r=scoped_report(c,request,start,end)
        out=StringIO(newline='');writer=csv.writer(out,delimiter=';')
        def safe(x):
            if isinstance(x,(int,float)):return x
            s='' if x is None else str(x)
            return "'"+s if s.startswith(('=','+','-','@','\t','\r')) else s
        def write(row):writer.writerow([safe(v) for v in row])
        write(['Период',start,end]);write(['Участок','План по проверенным строкам','Факт / потребность по проверенным строкам','Доля выполнения','Проверено строк','Всего строк','Полнота'])
        for area,t in r['totals'].items():write([AREAS[area],t.get('known_plan'),t.get('known_fact',t.get('known_need')),t.get('ratio'),t['valid_rows'],t['rows'],'Полные данные' if t['complete'] else 'Неполные данные'])
        write([]);write(['Партия','Факт заготовки','Потребность сварки','Дефицит (+) / избыток (-)','Замечания'])
        for b in r['batches']:write([b['batch_id'],b['fact'],b['need'],b['gap'],'; '.join(b['issues'])])
        write([]);write(['Первичные записи','Участок','record_id','Дата','Партия','Сотрудник','План','Факт','Потребность','Ошибки'])
        for x in r['records']+r['undated']:
            d=x['values'];write([x['id'],AREAS[x['area']],d.get('record_id'),d.get('date'),d.get('batch_id'),d.get('employee'),d.get('plan_qty',d.get('plan_docs')),d.get('fact_qty',d.get('fact_docs')),d.get('need_qty'),'; '.join(x['issues'])])
        return Response('\ufeff'+out.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="report-{start}-{end}.csv"'})
    @app.get('/api/pivot')
    def cross_tab(request:Request,start:str,end:str,area:str,group_by:str='employee'):
        if area not in AREAS:raise HTTPException(422,'Неизвестный участок')
        if not can_read(request.state.user,area):raise HTTPException(403,'Нет доступа к этому участку')
        from reporting import pivot
        with db() as c:r=scoped_report(c,request,start,end)
        try:return pivot(r,area,group_by)
        except ValueError as e:raise HTTPException(422,str(e))
    @app.get('/api/export.xlsx')
    def excel_export(request:Request,start:str,end:str,area:str='production',group_by:str='employee'):
        if area not in AREAS:raise HTTPException(422,'Неизвестный участок')
        if not can_read(request.state.user,area):raise HTTPException(403,'Нет доступа к этому участку')
        from reporting import build_xlsx
        with db() as c:r=scoped_report(c,request,start,end)
        try:content=build_xlsx(r,area,group_by)
        except ValueError as e:raise HTTPException(422,str(e))
        return Response(content,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        headers={'Content-Disposition':f'attachment; filename="operations-{start}-{end}.xlsx"'})
    @app.get('/')
    def home():return FileResponse(ROOT/'static'/'index.html',headers={'Cache-Control':'no-store'})
    app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
    register_workflow(app,db,read_rows,audit)
    register(app,db,audit)
    return app

app=create_app()
