import json
from types import SimpleNamespace
from PIL import Image
from localagent.base import Store
from localagent.app_bridge import AppBridge
from localagent.editorial import packets

def make_bridge(tmp_path):
    s=Store(tmp_path/'editorial.sqlite3');s.put('owner_chat',123)
    return AppBridge(SimpleNamespace(store=s))

def finish(b,text,heartbeat=True):
    if heartbeat:text+='\n<heartbeat><automation_id>telegram</automation_id><decision>NOTIFY</decision><message>Готово</message></heartbeat>'
    item={'id':'editorial-1','text':text,'phase':'final_answer'}
    b.finish({'id':'turn-editorial','items':[]},item)

def test_sections_are_delayed_deduplicated_and_routed(tmp_path):
    b=make_bridge(tmp_path)
    body='<!-- feed-post:news -->\n**Новости**\nИсточник, 24 октября.\n<!-- feed-post:memes -->\n**Мемы**\nhttps://www.tiktok.com/@demo/video/1'
    finish(b,body);finish(b,body)
    rows=b.store.rows('SELECT * FROM outbox ORDER BY id')
    assert len(rows)==2
    first,second=[json.loads(r['payload']) for r in rows]
    assert rows[1]['next_attempt']-rows[0]['next_attempt']==300
    assert first['news'] is True and second['news'] is False
    assert '#Новости' in first['text'] and '#Мемы' in second['text']
    assert 'Ответ из Codex' not in first['text'] and 'feed-post' not in first['text']
    assert first['editorial_slot']!=second['editorial_slot']

def test_photo_becomes_caption_without_duplicate_text(tmp_path,monkeypatch):
    b=make_bridge(tmp_path);p=tmp_path/'photo.jpg';Image.new('RGB',(40,40)).save(p)
    monkeypatch.setattr('localagent.app_bridge.linked_artifacts',lambda text:[p] if '![' in text else [])
    finish(b,f'<!-- feed-post:news -->\n**Новость**\nКороткий текст.\n![Фото: Автор, 24 октября]({p})')
    rows=b.store.rows('SELECT * FROM outbox')
    assert len(rows)==1 and rows[0]['method']=='photo'
    payload=json.loads(rows[0]['payload'])
    assert '**' not in payload['caption'] and 'Фото: Автор' in payload['caption']
    assert 'Короткий текст' in payload['caption'] and '![' not in payload['caption']

def test_plain_reply_is_immediate_even_with_marker(tmp_path):
    b=make_bridge(tmp_path);finish(b,'<!-- feed-post:news -->\nОбъяснение',False)
    row=b.store.rows('SELECT * FROM outbox')[0]
    assert row['next_attempt']==0
    assert 'editorial_slot' not in json.loads(row['payload'])

def test_empty_sections_are_skipped_and_count_is_bounded():
    assert packets('<!-- feed-post:news -->\n<!-- feed-post:memes -->\nТекст')==[('memes','Текст\n\n#Мемы')]
    assert len(packets(('<!-- feed-post:news -->\nТекст\n')*8))==4

def test_video_reply_uses_native_video_and_caption_without_link_wall(tmp_path,monkeypatch):
    b=make_bridge(tmp_path);p=tmp_path/'meme.mp4'
    p.write_bytes(b'\x00\x00\x00\x18ftypisom'+b'\0'*20)
    monkeypatch.setattr('localagent.app_bridge.linked_artifacts',lambda text:[p])
    finish(b,f'![Нулевой счёт, бесконечный вайб. Автор @demo]({p})',False)
    rows=b.store.rows('SELECT * FROM outbox')
    assert len(rows)==1 and rows[0]['method']=='video'
    payload=json.loads(rows[0]['payload'])
    assert payload['caption'].startswith('Нулевой счёт')
    assert payload['kind']=='meme' and payload['interactive']
    assert str(p) not in payload['caption']

def test_scheduled_video_is_one_caption_post_and_keeps_delay(tmp_path,monkeypatch):
    b=make_bridge(tmp_path);p=tmp_path/'meme.mp4'
    p.write_bytes(b'\x00\x00\x00\x18ftypisom'+b'\0'*20)
    monkeypatch.setattr('localagent.app_bridge.linked_artifacts',lambda text:[p] if '![' in text else [])
    finish(b,f'<!-- feed-post:memes -->\n**Вайб**\n![Автор @demo]({p})\n<!-- feed-post:facts -->\nФакт')
    rows=b.store.rows('SELECT * FROM outbox ORDER BY id')
    assert [r['method'] for r in rows]==['video','sendMessage']
    assert rows[1]['next_attempt']-rows[0]['next_attempt']==300
    assert 'Автор @demo' in json.loads(rows[0]['payload'])['caption']

def test_fake_mp4_is_not_routed_as_video(tmp_path):
    from localagent.app_bridge import artifact_method
    p=tmp_path/'fake.mp4';p.write_text('<html>not a video</html>')
    assert artifact_method(p)=='file'
