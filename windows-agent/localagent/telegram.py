from __future__ import annotations
import asyncio, json, re
from pathlib import Path
import httpx
from .base import ROOT, get_secret, redact,config
from .formatting import telegram_html,without_news_links

class Telegram:
    def __init__(self, token=None):
        self.token = token or get_secret('telegram')
        if not self.token:
            raise RuntimeError('Set Telegram token locally with manage.py secret telegram')
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(45,connect=15))
    async def call(self, method, **payload):
        try:
            r = await self.client.post(f'https://api.telegram.org/bot{self.token}/{method}',json=payload)
            obj = r.json()
        except Exception as e:
            raise RuntimeError('Telegram network error: '+type(e).__name__) from None
        if not obj.get('ok'):
            raise RuntimeError('Telegram API: '+redact(obj.get('description','error')))
        return obj['result']
    async def text(self, chat, value, news=False,reply_markup=None):
        value = redact(value)
        if news and config().get('hide_news_links',False):value=without_news_links(value)
        offset=0;results=[]
        while offset<len(value) or (offset==0 and not value):
            end=min(len(value),offset+3500)
            rendered=telegram_html(value[offset:end] or '—')
            while len(rendered)>3900:
                end=offset+max(1,(end-offset)//2);rendered=telegram_html(value[offset:end])
            extra={'reply_markup':reply_markup} if reply_markup and end==len(value) else {}
            results.append(await self.call('sendMessage',chat_id=chat,text=rendered,parse_mode='HTML',link_preview_options={'is_disabled':True},**extra))
            if not value:break
            offset=end
        return results
    async def file(self, chat, path, photo=False, caption='',news=False,reply_markup=None,video=False):
        path = Path(path)
        if news and config().get('hide_news_links',False):caption=without_news_links(caption)
        if path.stat().st_size > 49*1024*1024:
            raise ValueError('Telegram attachment exceeds 49 MB; split archive first')
        method, field = ('sendVideo','video') if video else (('sendPhoto','photo') if photo else ('sendDocument','document'))
        data={'chat_id':str(chat),'caption':redact(caption)[:900]}
        if video:data['supports_streaming']='true'
        if reply_markup:data['reply_markup']=json.dumps(reply_markup,ensure_ascii=False)
        try:
            with path.open('rb') as f:
                r = await self.client.post(f'https://api.telegram.org/bot{self.token}/{method}',
                    data=data,files={field:(path.name,f)},timeout=180)
            obj = r.json()
            if not obj.get('ok'):
                raise RuntimeError(redact(obj.get('description','upload error')))
            return obj['result']
        except httpx.HTTPError:
            raise RuntimeError('Telegram upload failed') from None
    async def voice(self,chat,path,caption=''):
        path=Path(path)
        if path.stat().st_size>49*1024*1024:raise ValueError('Voice file too large')
        try:
            with path.open('rb') as f:
                r=await self.client.post(f'https://api.telegram.org/bot{self.token}/sendVoice',data={'chat_id':str(chat),'caption':redact(caption)[:900]},files={'voice':(path.name,f,'audio/ogg')},timeout=180)
            obj=r.json()
            if not obj.get('ok'):raise RuntimeError(redact(obj.get('description','voice upload error')))
            return obj['result']
        except httpx.HTTPError:raise RuntimeError('Telegram voice upload failed') from None
    async def download(self, file_id, filename):
        meta = await self.call('getFile',file_id=file_id)
        if meta.get('file_size',0) > 20*1024*1024:
            raise ValueError('Incoming file is larger than Telegram getFile limit (20 MB)')
        safe = re.sub(r'[^\w. -]','_',Path(filename).name)[:140]
        import secrets
        path = ROOT/'inbox'/(secrets.token_hex(5)+'-'+safe)
        try:
            r = await self.client.get(f'https://api.telegram.org/file/bot{self.token}/{meta["file_path"]}')
            r.raise_for_status()
            if len(r.content) > 20*1024*1024:
                raise ValueError('File too large')
            path.write_bytes(r.content)
        except httpx.HTTPError:
            raise RuntimeError('Telegram download failed') from None
        return path
