import asyncio
from pathlib import Path
import httpx
from localagent.formatting import without_news_links
from localagent.telegram import Telegram


def test_news_sources_remain_named_but_urls_are_hidden():
    text='NASA: [Источник NASA](https://science.nasa.gov/article)\nФото ESA/NASA https://esa.int/photo\nwww.example.com\n[Письмо](https://mail.google.com/mail/u/0/#all/abc)'
    clean=without_news_links(text)
    assert 'NASA' in clean and 'ESA/NASA' in clean
    assert 'science.nasa.gov' not in clean and 'esa.int' not in clean and 'example.com' not in clean
    assert 'https://mail.google.com/mail/u/0/#all/abc' in clean


def test_text_filter_applies_only_to_news(monkeypatch):
    import localagent.telegram as module
    monkeypatch.setattr(module,'config',lambda:{'hide_news_links':True})
    async def run():
        tg=Telegram(token='test');sent=[]
        async def call(method,**kwargs):sent.append(kwargs['text']);return {}
        tg.call=call
        try:
            await tg.text(123,'NASA https://science.nasa.gov',news=True)
            await tg.text(123,'Документация https://science.nasa.gov')
        finally:await tg.client.aclose()
        assert 'https://' not in sent[0] and 'https://' in sent[1]
    asyncio.run(run())


def test_news_photo_caption_is_filtered_before_upload(tmp_path,monkeypatch):
    import localagent.telegram as module
    monkeypatch.setattr(module,'config',lambda:{'hide_news_links':True})
    path=tmp_path/'example.jpg';path.write_bytes(b'upload-test')
    uploaded=[]
    def handle(request):
        uploaded.append(request.content.decode('utf-8',errors='replace'))
        return httpx.Response(200,json={'ok':True,'result':{'message_id':1}})
    async def run():
        tg=Telegram(token='test');await tg.client.aclose()
        tg.client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
        try:await tg.file(123,path,photo=True,caption='ESA, 23.10.2026 https://esa.int/article',news=True)
        finally:await tg.client.aclose()
    asyncio.run(run())
    assert 'ESA, 23.10.2026' in uploaded[0] and 'https://esa.int/article' not in uploaded[0]
