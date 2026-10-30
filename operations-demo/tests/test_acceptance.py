import base64,csv,io,shutil,sqlite3
from pathlib import Path
from zipfile import ZipFile
from xml.sax.saxutils import escape
import pytest
from fastapi.testclient import TestClient
from app import create_app
from domain import FIELDS,parse_xlsx

PROD=[
 ['P-001','2026-10-05','LOT-01','Анна Соколова','100','90'],
 ['P-002','2026-10-06','LOT-02','Анна Соколова','100','100'],
 ['P-003','2026-10-07','LOT-03','Иван Морозов','100','1200'],
 ['P-004','2026-10-08','LOT-04','Иван Морозов','100','-5'],
 ['P-005','2026-10-09','LOT-05','Анна Соколова','100','80'],
 ['P-005','2026-10-09','LOT-05','Анна Соколова','100','80'],
 ['P-006','2026-10-12','LOT-06','Иван Морозов','100','0'],
 ['P-007','2026-10-13','LOT-07','Анна Соколова','100',''],
 ['P-008','2026-10-14','LOT-08','Иван Морозов','100','100'],
]
WELD=[[f'W-{i:03}',p[1],p[2],str(n)] for i,(p,n) in enumerate(zip(PROD[:5]+PROD[6:],[110,90,130,100,100,20,100,100]),1)]
DOCS=[['D-001','2026-10-05','Мария Лебедева','5','4'],['D-002','2026-10-06','Олег Волков','4','4'],['D-003','2026-10-07','Мария Лебедева','5','3'],['D-004','2026-10-09','Олег Волков','3','2'],['D-005','2026-10-12','Мария Лебедева','4','0'],['D-006','2026-10-14','Олег Волков','5','5']]

def fixture_xlsx(area,rows):
    """Minimal inert OOXML fixture, not a delivered workbook."""
    out=io.BytesIO()
    sheet='<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
    for i,row in enumerate([FIELDS[area]]+rows,1):
        sheet+=f'<row r="{i}">'+''.join(f'<c r="{chr(65+j)}{i}" t="inlineStr"><is><t>{escape(str(v))}</t></is></c>' for j,v in enumerate(row))+'</row>'
    sheet+='</sheetData></worksheet>'
    with ZipFile(out,'w') as z:
        z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Данные" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml',sheet)
    return out.getvalue()

def client(app,role='admin'):
    c=TestClient(app)
    login=c.post('/api/login',json={'username':role,'password':'demo-'+role+'-2026'})
    assert login.status_code==200
    c.headers['x-csrf-token']=login.json()['csrf']
    return c


@pytest.fixture
def demo(tmp_path):
    db=tmp_path/'data.sqlite3';inputs=tmp_path/'incoming';inputs.mkdir()
    files={}
    for area,rows in [('production',PROD),('welding',WELD),('docs',DOCS)]:
        p=inputs/(area+'.xlsx');p.write_bytes(fixture_xlsx(area,rows));files[area]=base64.b64encode(p.read_bytes()).decode()
    c=client(create_app(db))
    assert c.post('/api/import',json={'files':files}).status_code==200
    # The main acceptance condition: delete all three input files before edits.
    shutil.rmtree(inputs)
    return c,db,files

def report(c,start='2026-10-05',end='2026-10-14'):
    r=c.get('/api/report',params={'start':start,'end':end});assert r.status_code==200;return r.json()
def edit(c,record,**changes):
    v={**record['values'],**changes}
    r=c.put(f'/api/records/{record["area"]}/{record["id"]}',json={'values':v,'revision':record['revision']})
    assert r.status_code==200
def row(c,record_id):return next(x for x in c.get('/api/state').json()['rows'] if x['values']['record_id']==record_id)

def test_errors_propagate_but_independent_docs_stay_unchanged(demo):
    c,db,_=demo;r=report(c)
    assert r['issue_count']==5
    assert r['totals']['production']['known_fact']==290
    assert r['totals']['production']['ratio'] is None
    assert r['totals']['docs']['known_plan']==26 and r['totals']['docs']['known_fact']==18
    b=next(b for b in r['batches'] if b['batch_id']=='LOT-03');assert b['gap'] is None
    edit(c,row(c,'P-003'),fact_qty='120')
    after=report(c);b=next(b for b in after['batches'] if b['batch_id']=='LOT-03')
    assert b['gap']==10 and not b['issues']
    assert after['totals']['docs']==r['totals']['docs']
    assert after['daily']!=r['daily']
    # Restart an entirely new app against the persisted database, without inputs.
    restarted=client(create_app(db))
    assert row(restarted,'P-003')['values']['fact_qty']=='120'
    assert report(restarted)['batches']==after['batches']
    download=restarted.get('/api/export?start=2026-10-07&end=2026-10-07')
    assert download.status_code==200 and 'attachment' in download.headers['content-disposition']
    text=download.content.decode('utf-8-sig')
    assert 'LOT-03' in text and 'LOT-01' not in text and '120' in text

def test_all_error_fixes_zero_and_weighted_ratio(demo):
    c,_,_=demo
    duplicates=[r for r in c.get('/api/state').json()['rows'] if r['values']['record_id']=='P-005']
    assert all(not r['valid'] for r in duplicates)
    d=duplicates[-1];assert c.delete(f'/api/records/production/{d["id"]}?revision={d["revision"]}').status_code==200
    edit(c,row(c,'P-003'),fact_qty='120');edit(c,row(c,'P-004'),fact_qty='5');edit(c,row(c,'P-007'),fact_qty='100')
    r=report(c);p=r['totals']['production']
    assert r['issue_count']==0 and p['complete'] and p['known_plan']==800 and p['known_fact']==595
    assert p['ratio']==595/800
    zero=row(c,'P-006');assert zero['valid']
    assert next(b for b in r['batches'] if b['batch_id']=='LOT-06')['gap']==20
    first=report(c,'2026-10-05','2026-10-06')['totals']['production']
    assert first['known_plan']==200 and first['known_fact']==190 and first['ratio']==.95

def test_import_atomic_once_and_edit_conflict(demo):
    c,_,files=demo
    assert c.post('/api/import',json={'files':files}).status_code==409
    r=row(c,'P-001');edit(c,r,fact_qty='95')
    assert c.put(f'/api/records/production/{r["id"]}',json={'values':r['values'],'revision':r['revision']}).status_code==409
    assert c.put(f'/api/records/docs/{r["id"]}',json={'values':{},'revision':r['revision']}).status_code==404
    assert c.get('/api/report?start=2026-10-14&end=2026-10-05').status_code==422
    assert c.get('/api/report?start=bad&end=bad').status_code==422

def test_add_missing_dates_export_safety_and_crud(demo):
    c,db,_=demo
    created=c.post('/api/records/docs',json={'values':{'record_id':'D-new','date':'bad','employee':'=SUM(A1:A2)','plan_docs':'2','fact_docs':''}})
    assert created.status_code==200
    r=report(c);assert len(r['undated'])==1 and not r['totals']['docs']['complete']
    assert r['totals']['production']['known_fact']==290
    assert "'=SUM(A1:A2)" in c.get('/api/export?start=2026-10-05&end=2026-10-14').text
    ident=created.json()['id'];r=row(c,'D-new');edit(c,r,date='2026-10-10',fact_docs='0')
    assert row(c,'D-new')['valid']
    assert c.delete(f'/api/records/docs/{ident}?revision=2').status_code==200
    assert c.delete(f'/api/records/docs/{ident}?revision=2').status_code==404
    with sqlite3.connect(db) as conn:assert conn.execute("SELECT COUNT(*) FROM audit WHERE record=?",(ident,)).fetchone()[0]==3

def test_empty_period_and_initial_setup(tmp_path):
    c=client(create_app(tmp_path/'empty.sqlite3'))
    assert not c.get('/api/state').json()['initialized']
    assert c.post('/api/import',json={'files':{}}).status_code==422
    assert c.post('/api/records/docs',json={'values':{}}).status_code==409
    empty=report(c);assert empty['records']==[] and empty['totals']['docs']['ratio'] is None
    assert c.get('/').status_code==200 and c.get('/static/app.js').status_code==200

def test_failed_import_does_not_leave_partial_data(tmp_path):
    c=client(create_app(tmp_path/'empty.sqlite3'))
    files={a:base64.b64encode(fixture_xlsx(a,rows)).decode() for a,rows in [('production',PROD),('welding',WELD),('docs',DOCS)]}
    files['docs']=base64.b64encode(b'not xlsx').decode()
    assert c.post('/api/import',json={'files':files}).status_code==422
    assert c.get('/api/state').json()['rows']==[]
