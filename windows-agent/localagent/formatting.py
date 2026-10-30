"""Human-facing Telegram formatting. Raw tool data stays in local logs."""
import html,json,re
from urllib.parse import urlsplit
from datetime import datetime,timezone,timedelta

STATES={'queued':'⏳ В очереди','running':'⚙️ Выполняется','awaiting_approval':'✋ Ждёт согласия',
        'queued_in_codex':'📨 В очереди этого чата Codex','in_codex':'🧠 Выполняется в этом чате Codex',
        'completed':'✅ Готово','failed':'⚠️ Ошибка','cancelled':'⏹ Отменена','interrupted':'⚠️ Прервана — нужна проверка'}

def without_news_links(text):
    """Hide editorial URLs in the owner's news feed; preserve useful mailbox links."""
    def keep(url):
        try:return urlsplit(url).hostname in ('mail.google.com','calendar.google.com')
        except ValueError:return False
    def markdown(match):
        label,url=match.groups()
        return match.group(0) if keep(url) else label
    text=re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',markdown,str(text))
    text=re.sub(r'https?://[^\s<>\]\)]+',lambda m:m.group(0) if keep(m.group(0)) else '',text)
    text=re.sub(r'www\.[^\s<>\]\)]+','',text)
    return re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+','\n\n',text).strip()

def telegram_html(text):
    def link(match):
        label,target=match.group(1),match.group(2)
        if target.startswith(('https://','http://','tg://')):return label+'\n'+target
        return 'Файл прикреплён к задаче.' if re.search('архив|скачать|download',label,re.I) else label
    text=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,str(text))
    text=html.escape(str(text))
    text=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',text,flags=re.S)
    text=re.sub(r'`([^`\n]+)`',r'<code>\1</code>',text)
    text=re.sub(r'^#{1,3}\s+(.+)$',r'<b>\1</b>',text,flags=re.M)
    return text

def percent(n): return 'нет данных' if n is None else f'{n:.0%}'

def stats_report(obj):
    total=obj['total']
    if not total:
        return '**Отклики на hh.ru**\n\nИстория пока не подключена. Нужна авторизация hh.ru или импорт вашей истории.\n\nПросмотры, приглашения и отказы появятся после импорта.'
    return (f'**Отклики на hh.ru**\n\nВсего: {total}\nПриглашения: {percent(obj["invitation_rate"])}\n'
            f'Отказы: {percent(obj["rejection_rate"])}\nПодтверждённые просмотры: {percent(obj["explicit_view_rate"])}\n\n'
            'Причины отказов по этим данным установить нельзя. Статистика относится к доступной истории.')

def salary_text(s):
    if not s:return 'не указана'
    low,high=s.get('from'),s.get('to')
    def num(v):return f'{v:,.0f}'.replace(',',' ')
    amount=f'{num(low)}–{num(high)}' if low is not None and high is not None else f'от {num(low)}' if low is not None else f'до {num(high)}' if high is not None else 'не указана'
    return amount+' '+('₽' if s.get('currency')=='RUR' else s.get('currency',''))+(' до вычета налогов' if s.get('gross') else ' на руки' if s.get('gross') is False else '')

def vacancies_report(obj,limit=6):
    items=obj.get('selected',[])
    if not items:return '**Вакансии · Нижний Новгород**\n\nВ этой выборке подходящих вакансий не найдено. Попробуйте расширить поисковый запрос.'
    lines=['**Вакансии · Нижний Новгород**',f'Отобрано {len(items)} из {obj.get("fetched",len(items))} просмотренных. Порог — 80 000 ₽.','']
    for i,v in enumerate(items[:limit],1):
        office='офис подтверждён' if v.get('office_confirmed') else 'формат уточнить'
        floor=' · 80 000 ₽ не гарантированы' if v.get('salary_check')!='meets_floor' else ''
        lines += [f'**{i}. {v["title"]}**',str(v.get('employer') or ''),salary_text(v.get('salary'))+floor,office,v['url'],'']
    lines+=['Для оценки соответствия нужен ваш реальный опыт или резюме.']
    return '\n'.join(lines)

def tool_report(kind,result):
    if kind=='speak' and isinstance(result,dict) and result.get('voice'):return '🎙 Голосовое отправлено. Текст остаётся в исходном посте.'
    if kind=='diagnostics':return result['text']
    if isinstance(result,dict) and result.get('error'):
        err=result['error']
        if 'HH access restricted' in err:
            return '**hh.ru пока недоступен**\n\nСервис ограничил анонимный запрос. Для продолжения нужна официальная авторизация hh.ru. Обход CAPTCHA отключён.'
        return '**Не удалось выполнить действие**\n\n'+str(err)[:1200]
    if kind=='hh_search':return vacancies_report(result)
    if kind=='hh_history':return result.get('blocked') or stats_report(result)
    if kind=='windows':
        return '**Открытые окна**\n\n'+'\n'.join('• '+w['title'] for w in result[:25])
    if kind=='screenshot':return '**Снимок рабочего стола**\n\nПрикрепил файл выше.'
    if kind=='develop':return result.get('summary','Проект подготовлен; архив прикреплён.')
    if isinstance(result,dict) and result.get('blocked'):return result['blocked']
    return 'Действие выполнено.'

def friendly_error(error):
    value=str(error)
    if 'HH access restricted' in value:return 'hh.ru ограничил доступ. Нужна официальная авторизация; обход защиты отключён.'
    if 'Codex exit' in value:
        if any(w in value.lower() for w in ('usage limit','rate limit','quota')):return 'Достигнут лимит Codex. Повторите после его сброса.'
        return 'Codex вернул ошибку. Подробности сохранены в локальном журнале.'
    if not value or 'Timeout' in value:return 'Инструмент не ответил вовремя. Прогресс сохранён.'
    return value[:500]
