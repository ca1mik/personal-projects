"""Domain rules shared by dashboard, detail views and CSV export."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from io import BytesIO
from math import isfinite
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree as ET
import posixpath

AREAS = {'production': 'Заготовка', 'welding': 'Потребность сварки', 'docs': 'Документация'}
FIELDS = {
    'production': ['record_id','date','batch_id','employee','plan_qty','fact_qty'],
    'welding': ['record_id','date','batch_id','need_qty'],
    'docs': ['record_id','date','employee','plan_docs','fact_docs'],
}
NUMERIC = {'plan_qty','fact_qty','need_qty','plan_docs','fact_docs'}
LABELS = {'record_id':'номер записи','date':'дата','batch_id':'партия','employee':'сотрудник',
          'plan_qty':'план заготовки','fact_qty':'факт заготовки','need_qty':'потребность сварки',
          'plan_docs':'план документов','fact_docs':'факт документов'}
NS = {'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def parse_xlsx(raw, area):
    """Read values, never execute formulas or external links. Preserve dirty input."""
    if len(raw)>20*1024*1024: raise ValueError('Файл больше 20 МБ')
    try:
        with ZipFile(BytesIO(raw)) as z:
            if sum(i.file_size for i in z.infolist())>50*1024*1024:
                raise ValueError('Слишком большой распакованный файл')
            shared=[]
            if 'xl/sharedStrings.xml' in z.namelist():
                shared=[''.join(t.text or '' for t in el.findall('.//m:t',NS)) for el in ET.fromstring(z.read('xl/sharedStrings.xml'))]
            wb=ET.fromstring(z.read('xl/workbook.xml'))
            sheets=wb.find('m:sheets',NS)
            sheet=next((s for s in sheets if s.attrib['name']=='Данные'),None)
            if sheet is None: raise ValueError('Нужен лист «Данные»')
            rid=sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
            rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
            target=next(r.attrib['Target'] for r in rels if r.attrib['Id']==rid)
            target=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            root=ET.fromstring(z.read(target))
            epoch=wb.find('m:workbookPr',NS)
            epoch=date(1904,1,1) if epoch is not None and epoch.attrib.get('date1904') in ('1','true') else date(1899,12,30)
            rows=[]
            for row in root.findall('m:sheetData/m:row',NS):
                cells={}
                for c in row.findall('m:c',NS):
                    ref=c.attrib['r']; col=''.join(x for x in ref if x.isalpha())
                    v=c.find('m:v',NS); value=v.text if v is not None else ''
                    if c.attrib.get('t')=='s': value=shared[int(value)]
                    elif c.attrib.get('t')=='inlineStr': value=''.join(t.text or '' for t in c.findall('.//m:t',NS))
                    if c.find('m:f',NS) is not None: raise ValueError(f'В исходных данных {ref} содержит формулу. Передайте значения; расчёты выполняет система.')
                    cells[col]=value
                if any(v not in (None,'') for v in cells.values()):rows.append((int(row.attrib['r']),cells))
            if not rows: raise ValueError('Лист пуст')
            header={col:str(value).strip() for col,value in rows[0][1].items()}
            if set(FIELDS[area])-set(header.values()): raise ValueError('Колонки не соответствуют участку '+AREAS[area])
            result=[]
            for number,cells in rows[1:]:
                d={field: next((cells.get(col,'') for col,name in header.items() if name==field),'') for field in FIELDS[area]}
                try:
                    serial=float(d['date'])
                    d['date']=(epoch+timedelta(days=serial)).isoformat()
                except (ValueError,TypeError,OverflowError):pass
                result.append({'source_row':number,'values':d})
            if not result: raise ValueError('Нет записей для импорта')
            if len(result)>10000: raise ValueError('Для демо допускается до 10 000 записей на участок')
            return result
    except (BadZipFile,KeyError,ET.ParseError,StopIteration) as e:
        raise ValueError('Не удалось прочитать XLSX: неверная структура файла') from e

def quantity(value):
    if value is None or str(value).strip()=='':return None
    try:
        n=float(str(value).replace(',','.'))
        return n if isfinite(n) and n>=0 and n.is_integer() else None
    except (ValueError,TypeError):return None

def validate(rows):
    ids=Counter((r['area'],str(r['values'].get('record_id','')).strip()) for r in rows)
    output=[]
    for row in rows:
        r={**row,'issues':[]};d=r['values'];area=r['area']
        def issue(text):r['issues'].append(text)
        for field in FIELDS[area]:
            value=d.get(field)
            if value is None or str(value).strip()=='':issue('Не заполнено: '+LABELS[field])
            elif field in NUMERIC and quantity(value) is None:issue('Нужно целое неотрицательное число: '+LABELS[field])
        try:date.fromisoformat(str(d.get('date','')))
        except ValueError:issue('Некорректная дата')
        if ids[area,str(d.get('record_id','')).strip()]>1:issue('Повтор номера: проверьте обе записи')
        if area in ('production','docs'):
            suffix='qty' if area=='production' else 'docs'
            plan=quantity(d.get('plan_'+suffix));fact=quantity(d.get('fact_'+suffix))
            if plan is not None and fact is not None and fact>max(plan*3,0):
                issue('Подозрительный факт: больше трёх планов; требуется проверка')
        r['valid']=not r['issues'];output.append(r)
    return output

def summary(rows,start,end):
    # Validate before period filtering: a duplicate outside the period still matters.
    all_rows=validate(rows)
    selected=[r for r in all_rows if 'Некорректная дата' not in r['issues'] and start<=str(r['values'].get('date',''))<=end]
    undated=[r for r in all_rows if 'Некорректная дата' in r['issues']]
    groups={a:[r for r in selected if r['area']==a] for a in AREAS}
    totals={}
    for area,items in groups.items():
        valid=[r for r in items if r['valid']]
        suffix='qty' if area=='production' else 'docs'
        clean=bool(items) and len(valid)==len(items) and not any(r['area']==area for r in undated)
        t={'rows':len(items),'valid_rows':len(valid),'problem_rows':len(items)-len(valid),'complete':clean}
        if area=='welding':t['known_need']=sum(quantity(r['values']['need_qty']) for r in valid)
        else:
            t['known_plan']=sum(quantity(r['values']['plan_'+suffix]) for r in valid)
            t['known_fact']=sum(quantity(r['values']['fact_'+suffix]) for r in valid)
            t['ratio']=t['known_fact']/t['known_plan'] if clean and t['known_plan'] else None
        totals[area]=t
    prod=defaultdict(list);needs=defaultdict(list)
    for r in groups['production']:prod[str(r['values'].get('batch_id',''))].append(r)
    for r in groups['welding']:needs[str(r['values'].get('batch_id',''))].append(r)
    batches=[]
    for batch in sorted(set(prod)|set(needs)):
        p=prod[batch];w=needs[batch];issues=[]
        if not p:issues.append('Нет заготовок в выбранном периоде')
        if not w:issues.append('Нет потребности в выбранном периоде')
        if any(not r['valid'] for r in p):issues.append('Ошибки в заготовке')
        if any(not r['valid'] for r in w):issues.append('Ошибки в потребности')
        # Rows with unknown date cannot be safely assigned to or excluded from a period.
        if any(str(r['values'].get('batch_id',''))==batch and r['area'] in ('production','welding') for r in undated):issues.append('По партии есть запись без корректной даты')
        fact=sum(quantity(r['values']['fact_qty']) for r in p) if p and all(r['valid'] for r in p) else None
        need=sum(quantity(r['values']['need_qty']) for r in w) if w and all(r['valid'] for r in w) else None
        gap=need-fact if not issues else None
        batches.append({'batch_id':batch,'fact':fact,'need':need,'gap':gap,'issues':issues,'record_ids':[r['id'] for r in p+w]})
    daily=[]
    for day in sorted({str(r['values']['date']) for r in selected}):
        point={'date':day}
        for area in ('production','docs'):
            rs=[r for r in groups[area] if r['values']['date']==day];suffix='qty' if area=='production' else 'docs'
            point[area]=sum(quantity(r['values']['fact_'+suffix]) for r in rs) if rs and all(r['valid'] for r in rs) else None
            point[area+'_plan']=sum(quantity(r['values']['plan_'+suffix]) for r in rs) if rs and all(r['valid'] for r in rs) else None
        daily.append(point)
    return {'start':start,'end':end,'totals':totals,'batches':batches,'daily':daily,'records':selected,
            'undated':undated,'issue_count':sum(not r['valid'] for r in selected)+len(undated)}
