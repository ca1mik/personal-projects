import asyncio,json
import httpx
from localagent.telegram import Telegram
from localagent.base import Store
from localagent.experience import Experience
from types import SimpleNamespace

def test_upload_uses_sendvideo_streaming_and_keyboard(tmp_path):
    requests=[]
    def respond(request):
        requests.append(request)
        return httpx.Response(200,json={'ok':True,'result':{'message_id':123}})
    p=tmp_path/'clip.mp4';p.write_bytes(b'example-video')
    async def run():
        tg=Telegram('test-token')
        await tg.client.aclose()
        tg.client=httpx.AsyncClient(transport=httpx.MockTransport(respond))
        try:return await tg.file(1,p,video=True,caption='Шутка',reply_markup={'inline_keyboard':[]})
        finally:await tg.client.aclose()
    assert asyncio.run(run())['message_id']==123
    request=requests[0]
    assert request.url.path.endswith('/sendVideo')
    assert b'name="video"' in request.content
    assert b'name="supports_streaming"' in request.content
    assert b'name="reply_markup"' in request.content

def test_video_rating_is_attached_to_video_caption(tmp_path):
    s=Store(tmp_path/'video.sqlite3');ui=Experience(SimpleNamespace(store=s))
    decorated=ui.decorate({'id':3,'chat':1,'method':'video'},{'caption':'Игровая шутка','kind':'meme'})
    assert decorated
    post=ui.get(decorated[0],1)
    assert post['body']=='Игровая шутка' and post['kind']=='meme'
